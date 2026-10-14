# Work item: `member-docs-public-bucket`

## Summary

The PHI bucket `demo-health-member-docs` (`aws_s3_bucket.member_docs`, tags `Service=doc-service`, `DataClass=phi`) is world-readable. Two settings in `infra/s3.tf` cause this:

1. `aws_s3_bucket_public_access_block.member_docs` sets `block_public_acls`, `block_public_policy`, `ignore_public_acls` and `restrict_public_buckets` all to `false`.
2. `aws_s3_bucket_policy.member_docs` (Sid `AllowDocLinks`) allows `s3:GetObject` to `Principal "*"` on `${arn}/*`.

doc-service writes keys as `members/{member_ref}/{document_type}/{filename}` (`services/doc-service/doc_service/storage.py:7`). Anyone who has seen one key or guesses one can read members' documents (for example EOBs) with no authentication. This is CWE-284 / CWE-732.

**How it was confirmed:** a Terraform regression test (`infra/tests/member_docs_bucket.tftest.hcl`, mock AWS provider, no credentials) checks that all four BPA flags are `true` and that no bucket-policy statement Allows `Principal "*"`.

| Config | `terraform test` result |
|---|---|
| `main` | **fails both assertions**: all four BPA flags are `false`, and the policy Allows `Principal "*"` |
| fix branch, BPA fixed but the `main` policy kept | fails the `Principal "*"` assertion |
| fix branch | passes (`1 passed, 0 failed`). `terraform fmt -check -recursive` and `terraform validate` are clean |

The SIEM data shows the exposure was used: 1,463 anonymous GETs over 1,102 distinct keys in 24h, from hosting-provider and residential ASNs.

## Linked tickets

| Ticket | Source | Title |
|---|---|---|
| CSP-9080 | cloud_posture | S3.8 - S3 Block Public Access setting should be enabled at bucket level |
| CSP-9081 | cloud_posture | S3.2 - Bucket policy grants read to Principal '*' |
| PEN-2024-031 | pentest | Member documents retrievable without authentication |
| SIEM-88220 | siem_alert | Unauthenticated object reads on sensitive bucket |
| APP-2284 | app_bug | document links keep working after logout |

Not linked: CSP-9120 (same rule S3.2, but it is about `demo-health-static-site-assets`, which is `DataClass=public` and public by design). This change does not touch that bucket.

## Owning team

- **platform-eng** owns `infra/` (`ownership.yaml`, `CODEOWNERS /infra/`). It reviews and applies the Terraform PR.
- Routed to **secops** (the `escalation` for `infra` in `ownership.yaml`) for incident response, because the SIEM shows anonymous reads of PHI.
- Routed to **portal-eng** because removing public read breaks the portal's direct-object EOB links (APP-2284). The portal must serve documents through an authenticated route.
- FYI **docs-eng**: doc-service owns the bucket and its data (`Service=doc-service`, doc-service `data_class: phi`). No change is required from docs-eng for this fix.

## Severity

**Critical (Sev 0):** PHI in `demo-health-member-docs` is readable by anyone on the internet without authentication. The SIEM shows 1,102 distinct keys read anonymously in 24h, so this is a live security exposure of regulated data with no workaround.

## Blast radius

- **Data:** every object in `demo-health-member-docs`. This is member documents under `members/<ref>/<type>/<file>`, for example EOB PDFs. It is PHI: the bucket is tagged `DataClass=phi`, and doc-service is `data_class: phi` in `ownership.yaml`. Every member who has a stored document is potentially affected, not only the members whose links were shared. The key layout is predictable from `member_ref` and `document_type`.
- **Exposure window (observed):** cloud posture flagged the bucket on 2024-03-24 (CSP-9080/9081), the pentest confirmed it on 2024-03-31, and the SIEM saw mass anonymous reads on 2024-04-02. *Hypothesis:* the misconfiguration probably dates from when the bucket was created, so the real window may be longer. Access logs and CloudTrail data events need to be checked to establish it.
- **Services:**
  - doc-service writes to the bucket (`storage.py`, `DOCS_BUCKET`).
  - member-portal hands out document links (`config/default.json` `aws.docsBucket`; APP-2284). This fix intentionally breaks those direct links.
- **Roles and principals:**
  - Anonymous principal (`*`): the access that this fix removes.
  - `doc-service-prod` role: it can read and write this bucket through its wildcard policy. That is unaffected here; see `doc-service-iam-wildcard`.
  - `portal-svc` IAM user: its static key is leaked. That is unaffected here; see `portal-hardcoded-aws-key`.
- **Other groups:**
  - `portal-hardcoded-aws-key`: the leaked `portal-svc` key is configured for this same bucket (`aws.docsBucket`). SIEM-88190 shows that key calling `s3:ListBucket` from a hosting-provider IP (192.0.2.55). *Hypothesis:* that ListBucket targeted this bucket (the alert does not name the bucket). If so, an attacker could list every key and fetch each one anonymously, without guessing. Closing public read stops the anonymous GETs, but the leaked key keeps whatever S3 read access `portal-svc` has until it is rotated.
  - `doc-service-iam-wildcard` and `doc-yaml-rce`: the RCE on doc-svc-prod-01, combined with `Action "*"`/`Resource "*"`, gives an attacker this bucket's contents through the instance role. Those are separate paths to the same PHI, and this fix does not close them.
  - `claims-search-sqli` and `claims-idor`: different data store (claims DB). No overlap.

## Recommended action

**Root-cause fix (IaC, this PR → platform-eng):**

1. `aws_s3_bucket_public_access_block.member_docs`: set all four flags to `true`.
2. `aws_s3_bucket_policy.member_docs`: remove the `AllowDocLinks` public `s3:GetObject` statement. Replace it with a `DenyInsecureTransport` statement (deny `s3:*` when `aws:SecureTransport = false`), so that no statement allows public access.
3. Add the regression test `infra/tests/member_docs_bucket.tftest.hcl` (run with `terraform test` in `infra/`).
4. platform-eng: run `terraform plan` against prod before applying, and confirm that only the `member_docs` BPA and the policy change. After applying, check that an anonymous `GET https://demo-health-member-docs.s3.amazonaws.com/members/...` returns `403`.

**Before or alongside the apply (portal-eng):**

5. Stop handing out direct object URLs. Serve documents from an authenticated portal route that checks the session member owns `member_ref`, then streams the object or redirects to a short-lived (minutes) SigV4 presigned URL issued with role credentials. This fixes APP-2284 properly. Without it, EOB links return 403 once the IaC is applied.

**Incident response (secops):**

6. Preserve S3 server access logs and CloudTrail S3 data events for `demo-health-member-docs`, back to the bucket's creation.
7. Using those logs, list every key read by `requester=anonymous`. Map keys to `member_ref` to get the set of affected members. Separate pentest source IPs from everyone else.
8. Correlate with SIEM-88190 (`portal-svc` `s3:ListBucket` from 192.0.2.55) and the hosting-provider and residential ASNs in SIEM-88220. Decide whether key listing happened, and which bucket was listed.
9. Start the PHI breach-assessment and notification process with privacy/compliance for the affected members.
10. Once the change is applied, verify that the anonymous-read SIEM detector (`s3_anon_access`) goes quiet.

**Hardening follow-ups (platform-eng, optional, separate PRs):**

11. Enable account-level S3 Block Public Access, with an explicit exception process for `demo-health-static-site-assets`.
12. Set `aws_s3_bucket_ownership_controls` to `BucketOwnerEnforced` so object ACLs cannot be used.
13. docs-eng could consider non-guessable object keys as defence in depth.

## Status

PR opened
