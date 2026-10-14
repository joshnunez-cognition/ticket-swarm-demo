# Ticket groups: Demo Health security triage

40 tickets in, from 5 sources. They reduce to **6 root-cause groups (31 tickets)** plus **9 noise tickets**. Each group is one defect at one location; tickets were grouped only when the map evidence points at the same line or resource, not because they share a keyword. Per-ticket evidence is in [`triage/map_results.json`](triage/map_results.json).

## Summary

| Group | Root cause | Location | CWE | Tickets | Sources |
|---|---|---|---|---|---|
| `claims-search-sqli` | Claim search builds SQL with `%` string formatting on the user's search term | `services/claims-api/app/search.py:5-10` (`search_claims`) | CWE-89 | 6 | dependency_scanner, pentest, siem_alert, app_bug |
| `claims-idor` | `GET /claims/{claim_id}` looks a claim up by its sequential id without checking it belongs to the caller | `services/claims-api/app/routes.py:15-20` (`get_claim`) | CWE-639 | 5 | pentest, dependency_scanner, siem_alert, app_bug |
| `doc-yaml-rce` | The upload manifest is parsed with `yaml.load(..., Loader=yaml.Loader)` on request bytes, using vulnerable PyYAML 5.3.1 | `services/doc-service/doc_service/upload.py:15` (`parse_manifest`), `services/doc-service/requirements.txt:1` | CWE-502 | 5 | pentest, dependency_scanner, siem_alert |
| `doc-service-iam-wildcard` | The doc-service role's inline policy allows `Action "*"` on `Resource "*"`, and that role is on the doc-svc-prod-01 instance profile | `infra/iam.tf` `aws_iam_role_policy.doc_service` | CWE-269 | 5 | cloud_posture, pentest, siem_alert, app_bug |
| `member-docs-public-bucket` | The PHI bucket `demo-health-member-docs` has all four public-access-block flags off and a bucket policy granting `s3:GetObject` to `Principal "*"` | `infra/s3.tf` `aws_s3_bucket_public_access_block.member_docs` + `aws_s3_bucket_policy.member_docs` | CWE-284 / CWE-732 | 5 | cloud_posture, pentest, siem_alert, app_bug |
| `portal-hardcoded-aws-key` | A static AWS access key pair for `portal-svc` (with the region) is committed in the portal config | `services/member-portal/config/default.json:4-9` (`aws.*`) | CWE-798 | 5 | pentest, dependency_scanner, cloud_posture, siem_alert, app_bug |

---

## `claims-search-sqli`

**Root cause:** `search_claims()` interpolates `member_id` and the search term into SQL with `%`: `"... WHERE member_id = '%s' AND description LIKE '%%%s%%' ..." % (member_id, term)`. It then runs the result with `db().execute(query)` and binds no parameters. A quote in `q` breaks out of the string literal. A malformed term raises a sqlite error (500), and `' OR '1'='1` drops the `member_id` scope and returns every member's claims. The map worker reproduced it locally: `q=%' OR 1=1 --` returned all 5 seed claims across members.

| Ticket | Source | Title | Why it belongs |
|---|---|---|---|
| SCA-4471 | dependency_scanner | SAST: Possible SQL injection (CWE-89) | Rule `py/sql-string-format` flags exactly the `%`-formatted query that reaches `execute()` in `search.py`. This is the static view of the defect. |
| PEN-2024-017 | pentest | Authenticated SQL injection in claims search endpoint | `' OR '1'='1` in the search parameter returned other members' claims. That only works because the term is concatenated into the `LIKE '%...%'` clause. |
| PEN-2024-019 | pentest | Verbose database errors returned to client | Malformed search input makes the concatenated query invalid and the request 500s. The 500 is a symptom of the same unparameterized query. On `main`, FastAPI's default handler returns a generic `Internal Server Error` body, so the verbose-message part did not reproduce. The ticket still traces to the same line. |
| SIEM-88241 | siem_alert | WAF signature match: SQLI_PATTERN_UNION_SELECT (x37) | 37 SQLi signature matches on `uri /claims/search`, which is the route that calls `search_claims`. The WAF was in COUNT mode, so the payloads reached the vulnerable code. This is the runtime attack traffic. |
| SIEM-88310 | siem_alert | Anomalous query volume - claims-api-prod-01 | One caller got ~350x the normal p99 row count (12 -> 4180). The IDOR endpoint returns one row per request, so it can't move rows-per-query. An injected `OR` condition on the unbounded search query can. This is the data-volume signal of successful exploitation. |
| APP-2291 | app_bug | search box breaks when you type an apostrophe | `O'Neill` closes the `'%...%'` literal early, which gives a SQL syntax error ("unterminated string") and a 500. That is the same quote-injection, triggered by accident. |

## `claims-idor`

**Root cause:** `get_claim()` runs `SELECT * FROM claims WHERE id = ?` with only `claim_id` and returns the row. The authenticated `user` from `Depends(current_user)` is never compared with `row["member_id"]`, and no role is checked. Claim ids are small sequential integers (1001-1005 in `db.py`), so enumeration is trivial. The query is parameterized, so this is a separate defect from the SQL injection.

| Ticket | Source | Title | Why it belongs |
|---|---|---|---|
| PEN-2024-021 | pentest | Insecure direct object reference - any claim readable by any member | Changing the numeric id on the claim-detail request returned other members' claims. That is exactly the missing ownership check in `get_claim`. |
| SCA-4480 | dependency_scanner | SAST: Route handler with no authorization check (CWE-639) | Rule `py/missing-authz-on-resource` in `services/claims-api/app`. The only route that takes a path identifier is `/claims/{claim_id}`, and it resolves the id without comparing it to the principal. |
| SIEM-88275 | siem_alert | Sequential resource enumeration detected | `token-***bob` (m-200) hit `/claims/{id}` with 612 distinct ids and got 598 `200`s in 9 minutes. A member can only read other members' claims if the ownership check is missing. |
| PEN-2024-026 | pentest | Claim identifiers are predictable | Incrementing integer ids are what make the IDOR bulk-exploitable, and the finding explicitly pairs with the detail-endpoint access control. Same endpoint, same fix surface: an authorization check, plus optionally non-guessable ids. |
| APP-2305 | app_bug | member saw someone else's claim | A claim-detail page showed another member's claim. The portal has no claim-detail route of its own, so detail comes from `claims-api` `get_claim`, which returns any id to any member. The exact bookmark mechanism is unconfirmed, but no other code path serves another member's claim detail. |

## `doc-yaml-rce`

**Root cause:** `parse_manifest()` runs `yaml.load(raw, Loader=yaml.Loader)` on the unauthenticated `POST /upload` body (`app.py:11-15`). The full Loader builds arbitrary Python objects (`!!python/object/apply:os.system`), which gives code execution as the doc-service process on doc-svc-prod-01. The pinned `PyYAML==5.3.1` is also affected by CVE-2020-14343, which is the same class of bug in the same call.

| Ticket | Source | Title | Why it belongs |
|---|---|---|---|
| SCA-4403 | dependency_scanner | SAST: Unsafe YAML deserialization (CWE-502) | Points directly at `yaml.load()` with `yaml.Loader` on request-controlled bytes in doc-service. This is the line itself. |
| SCA-4402 | dependency_scanner | PyYAML 5.3.1 - CVE-2020-14343 | The CVE is code execution "when processing untrusted YAML with the full Loader". `requirements.txt` pins 5.3.1, and `upload.py:15` is the reachable full-Loader call on untrusted input, so the CVE is reachable through this defect. |
| PEN-2024-023 | pentest | Remote code execution via config/manifest upload | A python object constructor tag in the upload manifest executed commands (DNS callout, sleep). That is exactly what `yaml.Loader` allows in `parse_manifest`. |
| SIEM-88140 | siem_alert | Shell spawned by application process (doc-svc-prod-01) | Parent `python3 -m doc_service.app`, child `/bin/sh -c id`. A shell spawned by the doc-service process on its host is the runtime footprint of `!!python/object/apply:os.system` from the manifest parser. |
| SIEM-88102 | siem_alert | Unexpected outbound connection from doc-svc-prod-01 | First-seen `python3` egress to `203.0.113.77:443` (215 KB out) from the same host. This is consistent with the pentest DNS callout or post-exploitation via the same RCE, and the host normally egresses only to the package mirror. |

## `doc-service-iam-wildcard`

**Root cause:** `aws_iam_role_policy.doc_service` (`doc-service-access`) grants `Effect Allow, Action "*", Resource "*"` to role `doc-service-${var.env}` (`doc-service-prod`). That role is on `aws_iam_instance_profile.doc_service`, which is attached to `aws_instance.doc_service` (Name `doc-svc-prod-01`). The service only needs `s3:PutObject`/`GetObject` on its own docs bucket. By contrast, `aws_iam_role_policy.claims_api` is correctly scoped to `secretsmanager:GetSecretValue` on `claims-api/*`.

| Ticket | Source | Title | Why it belongs |
|---|---|---|---|
| CSP-9075 | cloud_posture | IAM.1 - Policies should not allow full '*' administrative privileges | Names the exact inline policy `doc-service-access` on `role/doc-service-prod` with `*`/`*`, which is `aws_iam_role_policy.doc_service`. |
| CSP-9098 | cloud_posture | Privilege escalation path: instance profile to admin | The doc-svc-prod-01 instance profile -> role -> wildcard policy, which covers `iam:*`/`sts:*`. The chain is `compute.tf` `iam_instance_profile` -> `aws_iam_instance_profile.doc_service` -> the wildcard policy. |
| PEN-2024-034 | pentest | Excessive instance role permissions amplify host compromise | After host execution, the role could read unrelated storage and create principals. Only the `*`/`*` policy allows that. The pentest's own recommendation is to scope this policy. |
| SIEM-88165 | siem_alert | Role credentials used for unusual API calls | `doc-service-prod` called `iam:ListRoles`, `s3:ListAllMyBuckets`, `secretsmanager:ListSecrets` through instance metadata. These calls succeeded beyond the s3 Put/Get baseline only because the policy allows every action. |
| APP-2301 | app_bug | doc-service can write to buckets it shouldn't | The ingest job wrote to the analytics bucket, which "nobody granted explicitly". `Resource "*"` with `Action "*"` is that implicit grant. |

Note: this is the **blast-radius amplifier** for `doc-yaml-rce`. The RCE gives code execution, and this policy turns it into account-wide access. They are separate defects with separate fixes and owners: code for docs-eng, IaC for platform-eng.

## `member-docs-public-bucket`

**Root cause:** `aws_s3_bucket.member_docs` (`demo-health-member-docs`, `DataClass=phi`) has two problems. `aws_s3_bucket_public_access_block.member_docs` sets all four flags to `false`. And `aws_s3_bucket_policy.member_docs` (Sid `AllowDocLinks`) grants `s3:GetObject` to `Principal "*"` on `/*`. Doc-service writes keys as `members/{member_ref}/{document_type}/{filename}` (`storage.py:7`), so anyone holding or guessing a key can read PHI with no auth. The disabled block and the public policy are the two halves of one exposure on one resource, and one change fixes both.

| Ticket | Source | Title | Why it belongs |
|---|---|---|---|
| CSP-9080 | cloud_posture | S3.8 - Block Public Access should be enabled at bucket level | `demo-health-member-docs` has all four BPA settings disabled. That is `aws_s3_bucket_public_access_block.member_docs`, all `false`. |
| CSP-9081 | cloud_posture | S3.2 - Bucket policy grants read to Principal '*' (member-docs) | A public `s3:GetObject` statement on `demo-health-member-docs/*`. That is `aws_s3_bucket_policy.member_docs` `AllowDocLinks`. |
| PEN-2024-031 | pentest | Member documents retrievable without authentication | Unauthenticated GETs worked, and keys follow the predictable `members/<ref>/<type>/<file>` layout. That matches the public policy plus the `object_key()` format in `storage.py`. |
| SIEM-88220 | siem_alert | Unauthenticated object reads on sensitive bucket | 1,463 anonymous GETs over 1,102 distinct keys on `demo-health-member-docs` in 24 hours. Anonymous reads are only possible because of `Principal "*"` with BPA off. |
| APP-2284 | app_bug | document links keep working after logout | EOB links open in a private window with no session. The link is a direct object URL on a world-readable bucket, so the portal session plays no part. |

## `portal-hardcoded-aws-key`

**Root cause:** `services/member-portal/config/default.json` commits `aws.accessKeyId` (`AKIA...MPLE`), `aws.secretAccessKey`, `aws.region: "us-east-1"` and `aws.docsBucket`. `src/config.js` `loadConfig()` reads only that file and has no env/role override. The credential is the long-lived key of IAM user `portal-svc`, it is in git history (`f9af89b`), and it ships in every build artifact. The values match AWS's documentation example pair, but in this scenario the tickets treat it as the live `portal-svc` key, so it is handled as exposed. **This needs incident response (rotate, review usage, purge history), not just a code change.**

| Ticket | Source | Title | Why it belongs |
|---|---|---|---|
| SCA-4455 | dependency_scanner | Secret detected: AWS access key id (CWE-798) | 20-char AKIA id plus a 40-char secret in a committed JSON config under `services/member-portal/config`, present in history. That is `default.json:6-7`. |
| PEN-2024-029 | pentest | Static cloud credentials shipped with the portal application | A static key pair in the deployed portal bundle's configuration instead of a role or secret reference. That is the same file, bundled. |
| CSP-9112 | cloud_posture | IAM user with long-lived access key (key age 412 days) | `portal-svc` has one active key that hasn't been rotated in 412 days. A key hardcoded in committed config can't be rotated without a code change, which is why it is stale. `infra/` has no `aws_iam_user`, so the key isn't managed anywhere else in the repo. |
| SIEM-88190 | siem_alert | API call from access key outside normal network | Key `AKIA...MPLE` (`portal-svc`) called `s3:ListBucket` from a hosting-provider IP outside the VPC. The key suffix matches `AKIAIOSFODNN7EXAMPLE` in `default.json`. Use from outside the VPC is what you'd expect once the key has leaked through the repo or artifacts. |
| APP-2268 | app_bug | portal deploy to the new region failed, wrong credentials? | The DR deploy to us-west-2 got 403s, and the dev said the region "is hardcoded ... in the config with the keys". That is the same `aws` block in `default.json`: static `portal-svc` credentials plus `region: us-east-1`, which `loadConfig()` cannot override. Moving to role credentials and env-provided region/bucket fixes this ticket and the leak together. (Map confidence 0.6. The exact 403 path is unconfirmed, but no other region or credential config exists for the portal.) |

---

## Noise / not grouped (9)

| Ticket | Source | Title | Reason |
|---|---|---|---|
| CSP-9131 | cloud_posture | ACM certificate expires in 12 days | **Unrelated to the repo.** An imported ACM cert for `status.example.com`. There's no ACM resource or status host anywhere in `infra/` or the services. Ops renewal task. |
| SIEM-88260 | siem_alert | Rate limit threshold exceeded - public marketing site | **Benign, not in repo.** WAF rate limit on the CloudFront marketing site blocked a crawler, which then respected robots. No CloudFront/WAF resources in `infra/`, and the control worked as intended. |
| SIEM-88230 | siem_alert | DLP: PII pattern in outbound attachment (resolved) | **Already resolved / not in repo.** Corp laptop DLP block. The review says "test fixture file with synthetic values, closed". |
| SIEM-88199 | siem_alert | EDR: generic trojan detection on build agent (false positive) | **False positive.** Heuristic hit on a packed `esbuild` binary in the npm cache. The analyst confirmed a known FP and allowlisted the hash. No build-agent config in the repo, and esbuild isn't a dependency. |
| APP-2275 | app_bug | MFA reset request - contractor laptop replaced | **IT helpdesk request.** Identity-provider MFA re-enrollment. No IdP code in the repo. |
| APP-2259 | app_bug | suspicious email reported by employee | **Corporate phishing report.** Look-alike domain, no credentials entered, already forwarded to the mailbox team. Nothing in the repo. |
| CSP-9120 | cloud_posture | S3.2 - Bucket policy grants read to Principal '*' (static-site-assets) | **Looks related but isn't (false positive).** Same rule ID and wording as CSP-9081, but the bucket is `demo-health-static-site-assets`: tagged `DataClass=public`, `Purpose=public-website`, commented `# Marketing site assets. Public by design` (`infra/s3.tf:31`). The policy is `PublicWebsiteRead` `s3:GetObject` only, with `block_public_acls`/`ignore_public_acls = true`. The ticket itself says "rule default, context not evaluated". |
| APP-2312 | app_bug | secure message inbox times out for long-tenure members | **Looks related but isn't.** Tagged as "the injection thing", but `messages.js` `INBOX_SQL` uses `?` placeholders and `searchInbox` binds `[memberId, `%${term}%`]`, so it is parameterized. The timeout is the missing `(member_id, created_at)` index called out in the file's own comment (`messages.js:1-2`). Performance bug for portal-eng, not a security defect. |
| APP-2240 | app_bug | upload hangs on large YAML manifests | **Looks related but isn't.** It touches the same `parse_manifest` line as `doc-yaml-rce`, but the input is a legitimate ~4 MB ops manifest, under `MAX_UPLOAD_BYTES` (5 MB). The hang is the pure-Python YAML parser running synchronously on a single-threaded `wsgiref` server (`app.py:28`). There is no exploitation, and switching to `safe_load` would not fix the slowness (it's also pure-Python). Performance bug for docs-eng. |
