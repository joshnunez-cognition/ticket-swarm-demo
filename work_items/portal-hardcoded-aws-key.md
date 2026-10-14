# Work item: `portal-hardcoded-aws-key`

## Summary

The member portal commits a static AWS access key pair for IAM user `portal-svc` in `services/member-portal/config/default.json` (`aws.accessKeyId` `AKIA...MPLE`, `aws.secretAccessKey`, plus `aws.region: "us-east-1"` and `aws.docsBucket: "demo-health-member-docs"`). `src/config.js` `loadConfig()` reads only that file, so nothing in the environment or an instance role can override it. The key has been in git history since the first commit (`f9af89b`) and ships in every package built from the service. SIEM shows the key being used from outside the VPC. CWE-798.

The values are AWS's published documentation example pair. The tickets treat this as the live `portal-svc` key, so this work item handles it as an **exposed, actively used credential**. The real fix is incident response (revoke/rotate, review usage, purge history) owned by portal-eng and secops, so this group gets **no PR**.

### Evidence (observed on `main` @ `9268796`)

- `config/default.json:5-8` holds `region`, `accessKeyId` (`AKIAIOSFODNN7EXAMPLE`), `secretAccessKey` and `docsBucket`. Map evidence: `triage/map_results.json` (PEN-2024-029, SCA-4455, CSP-9112, SIEM-88190 at 0.7-0.95 confidence).
- **History:** `git log --all -- services/member-portal/config/default.json` lists only `f9af89b`. `git show f9af89b:services/member-portal/config/default.json` contains `AKIAIOSFODNN7EXAMPLE` on line 6. Deleting the file in a new commit would leave the key in history.
- **Build artifact:** `npm pack --dry-run` in `services/member-portal` includes `config/default.json` (303B). `package.json` has no `files` allow-list and `.gitignore` does not exclude `config/`.
- **No override path:** I ran `AWS_REGION=us-west-2 PORTAL_DOCS_BUCKET=x AWS_ACCESS_KEY_ID=ROLE node -e 'console.log(JSON.stringify(require("./src/config").loadConfig().aws))'`. It printed `{"region":"us-east-1","accessKeyId":"AKIAIOSFODNN7EXAMPLE",...,"docsBucket":"demo-health-member-docs"}`, so the env vars were ignored. This reproduces the APP-2268 mechanism (the region can't be changed for the DR deploy).
- **Not managed in IaC:** `infra/` has no `aws_iam_user`, access key, or member-portal role/instance profile. `portal-svc` and its key are created outside this repo.
- Existing service tests pass on `main` (`npm ci && npm test`: 3 pass, 0 fail). None of them cover config loading.

## Linked tickets

| ID | Source | Title |
|---|---|---|
| SCA-4455 | dependency_scanner | Secret detected: AWS access key id (CWE-798) |
| PEN-2024-029 | pentest | Static cloud credentials shipped with the portal application |
| CSP-9112 | cloud_posture | IAM user with long-lived access key (key age 412 days) |
| SIEM-88190 | siem_alert | API call from access key outside normal network |
| APP-2268 | app_bug | portal deploy to the new region failed, wrong credentials? |

## Owning team

- **Owner: portal-eng** (`ownership.yaml` `services.member-portal.team`; `#portal-eng`, portal-eng-oncall@example.com; CODEOWNERS `/services/member-portal/` -> `@demo-health/portal-eng`).
- **Routed to: secops** (`#secops`, secops-oncall@example.com) for incident response: credential revocation, CloudTrail review, history purge, and deciding on any breach determination. secops is also the CODEOWNERS default (`*`).
- Dependency, not routed here: portal-eng will need platform-eng to add a member-portal IAM role/instance profile in `infra/` (none exists today) as part of step 6 below. portal-eng/secops should raise that with `#platform-eng`.

## Severity

**Critical (Sev 0).** A long-lived cloud credential is leaked in git history and in every build artifact. SIEM-88190 shows it being used from a hosting-provider IP outside the VPC, and the principal reaches the PHI bucket `demo-health-member-docs`. Rubric: a leaked secret is a security exposure, which is Sev 0, page the owner.

## Blast radius

- **Data:** member-portal is `data_class: pii` (`ownership.yaml`). The key's configured `docsBucket` is `demo-health-member-docs`, which `infra/s3.tf` tags `DataClass = phi` and `Service = doc-service`. So the exposed principal reaches **PHI** as well as the portal's PII.
- **Principal:** IAM user `portal-svc`, one active key, not rotated in 412 days, last used 2 days before CSP-9112 (CSP-9112). Its attached policies are **not visible in this repo** (the user isn't in `infra/`). Its real permissions are unknown and must be pulled from IAM. At minimum, SIEM shows it can call `s3:ListBucket`.
- **Exposure surface:** anyone with read access to the repo (any clone or fork, including history), and anyone holding a portal build artifact or deployed bundle (PEN-2024-029).
- **Observed misuse:** SIEM-88190 (2024-04-01T13:48Z): `portal-svc` / `AKIA...MPLE` called `s3:ListBucket` from `192.0.2.55` (ASN hosting-provider), not the usual `vpc-0a1b2c3d`. The bucket is not named in the alert.
- **Services:** member-portal (credential consumer). doc-service (owns the bucket the key points at). DR environment in us-west-2 (blocked, APP-2268).
- **Cross-group links:**
  - `member-docs-public-bucket` (platform-eng): same bucket. *Hypothesis, not verified:* `ListBucket` with this key returns the object keys (`members/{member_ref}/...`), and the bucket's `Principal "*"` `s3:GetObject` policy then lets anyone read them with no credentials. The timing fits: SIEM-88190 (ListBucket from hosting-provider, 04-01 13:48Z) comes about 17h before SIEM-88220 (1,463 anonymous GETs over 1,102 distinct keys from hosting-provider/residential ASNs, 04-02 07:19Z). Confirming this needs CloudTrail data events plus S3 access logs (step 3). If it holds, this group's leak is how the attacker found the keys for that group's exposure, and the two incidents should be handled as one PHI incident.
  - `doc-service-iam-wildcard`: no direct link. That is a different principal (role `doc-service-prod`). It only matters if `portal-svc` turns out to hold IAM permissions that could reach that role.
  - `claims-search-sqli`, `claims-idor`, `doc-yaml-rce`: no link found.
  - APP-2312 (portal inbox timeout, noise) is in the same service but unrelated.

## Recommended action

Outcome: **no PR from this group.** The root-cause fix is credential incident response. A code change alone wouldn't revoke the key or remove it from history or from artifacts already distributed.

Numbered response plan:

1. **Contain now (secops + portal-eng, page on-call):** deactivate the `portal-svc` access key `AKIA...MPLE` (`aws iam update-access-key --status Inactive`), then delete it once the service no longer depends on it. Review and strip any other credentials or console access on `portal-svc`. Expect the prod portal's document features to stop working until step 6 ships. Accept that or bridge it with a short-lived, tightly scoped interim key held in a secret manager, never in the repo.
2. **Scope the principal (secops):** pull the attached and inline policies of `portal-svc` (`aws iam list-attached-user-policies` / `list-user-policies`) to see exactly what the leaked key could do. Check for any IAM write permissions.
3. **Review usage (secops):** query CloudTrail, including S3 data events, for every call by `AKIA...MPLE` over the key's life (412 days), and at minimum since the first commit. Focus on calls from outside `vpc-0a1b2c3d`, `192.0.2.55`, and any other hosting-provider ASNs. Correlate with S3 server access logs for `demo-health-member-docs` against the SIEM-88220 window to confirm or rule out the ListBucket-to-anonymous-GET hypothesis above. Look for persistence (new users, keys, roles, or policy changes).
4. **Breach determination (secops + compliance):** if step 3 shows PHI/PII objects were listed or read, treat it as a reportable PHI incident jointly with `member-docs-public-bucket`. Record the affected member refs from the object keys.
5. **Purge the secret (portal-eng with secops):** remove the `aws` credential fields from `config/default.json`, rewrite git history to drop them from `f9af89b` onward (`git filter-repo` / BFG), force-push, ask everyone to re-clone, and invalidate caches and forks where possible. Withdraw or rebuild published portal artifacts and container images that contain `config/default.json`. Revocation (step 1) is the real control. The purge only limits further spread.
6. **Root-cause code/IaC fix (portal-eng, with platform-eng for the role):** change `loadConfig()` to take `region` and `docsBucket` from the environment (for example `AWS_REGION` / `PORTAL_DOCS_BUCKET`, falling back to defaults that contain no credentials) and to read no keys from the file. Let the AWS SDK default credential chain use a member-portal instance/task role scoped to what the portal actually needs (for example `s3:GetObject` on the docs prefix, not `ListBucket` on the whole bucket). Add a regression test that `config/default.json` holds no `accessKeyId`/`secretAccessKey` and that the env override for region/bucket works. Add a `files` allow-list or build exclusion so config secrets can't be packaged again. This also resolves **APP-2268**: the DR deploy can set `AWS_REGION=us-west-2` and the DR bucket.
7. **Prevent recurrence (secops / platform-eng):** turn on push-protection secret scanning for the repo (SCA-4455 only caught this after the fact). Add an SCP or alert on IAM user access-key creation for service principals. Close CSP-9112 by retiring IAM-user keys for services rather than rotating them.
8. **Close-out:** link the CloudTrail findings to SIEM-88190, close SCA-4455 / PEN-2024-029 / CSP-9112 after steps 1, 5 and 6, close APP-2268 after the DR re-test passes, and have the pentest vendor re-test PEN-2024-029.

## Status

**Triaged and routed** to portal-eng (owner) and secops (incident response). No PR. Code change specified in step 6, to land after containment.
