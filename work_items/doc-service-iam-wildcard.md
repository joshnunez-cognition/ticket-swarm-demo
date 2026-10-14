# Work item: `doc-service-iam-wildcard`

## Summary

The inline policy `aws_iam_role_policy.doc_service` (`doc-service-access`, `infra/iam.tf`) granted `Effect Allow, Action "*", Resource "*"` to role `doc-service-${var.env}` (`doc-service-prod`). That role sits on `aws_iam_instance_profile.doc_service`, which is attached to `aws_instance.doc_service` (`doc-svc-prod-01`, `infra/compute.tf`). Any code running on that host could therefore use instance-metadata credentials as an account administrator of `111122223333`, including `iam:*` and `sts:*`. The service itself only calls `client.put_object(Bucket=BUCKET, ...)` on `demo-health-member-docs` (`services/doc-service/doc_service/storage.py`). Its documented baseline is `s3:PutObject`/`s3:GetObject`.

Root cause confirmed on `main`. A new Terraform test (`infra/tests/doc_service_iam.tftest.hcl`, mock AWS provider, `terraform test`) fails on `main` with `policy is "{\"Statement\":[{\"Action\":\"*\",\"Effect\":\"Allow\",\"Resource\":\"*\"}],...}"` and passes on the fix branch.

Classification: **infrastructure / IAM misconfiguration (CWE-269)**. The fix is IaC, so a PR goes to platform-eng. SIEM-88165 shows signs of exploitation, so incident-response follow-ups for secops are listed under Recommended action.

## Linked tickets

| Ticket | Source | Title |
|---|---|---|
| CSP-9075 | cloud_posture | IAM.1 - Policies should not allow full '*' administrative privileges |
| CSP-9098 | cloud_posture | Privilege escalation path: instance profile to admin |
| PEN-2024-034 | pentest | Excessive instance role permissions amplify host compromise |
| SIEM-88165 | siem_alert | Role credentials used for unusual API calls |
| APP-2301 | app_bug | doc-service can write to buckets it shouldn't |

## Owning team

- **platform-eng** (owner of `infra/` in `ownership.yaml` and `CODEOWNERS`): owns the Terraform fix and the PR. Contact `#platform-eng`, platform-oncall@example.com.
- Routed to **secops** (the `infra` escalation in `ownership.yaml`): incident response for the role-credential misuse in SIEM-88165. Contact `#secops`, secops-oncall@example.com.
- FYI to **docs-eng** (owner of `doc-service`): confirm the scoped permission set covers every runtime path, and stop the ingest job writing to the analytics bucket (APP-2301).

## Severity

**Critical (Sev 0).** An admin-equivalent role is reachable from a host with an unauthenticated RCE (`doc-yaml-rce`), its credentials have already been used for first-seen IAM/S3/Secrets Manager enumeration (SIEM-88165), and it exposes PHI and account-wide privilege escalation.

## Blast radius

- **Account:** all of AWS account `111122223333`. `Action "*"`/`Resource "*"` includes `iam:*` (create users, access keys, roles, or policies for persistence), `sts:*` (assume other roles), and destructive actions on every resource.
- **Data (`ownership.yaml` `data_class`):**
  - `phi`: `demo-health-member-docs` (doc-service, tagged `DataClass=phi`). The role can read, write, and delete every object in it, plus change its bucket policy and public-access block.
  - `phi`: claims-api data. `secretsmanager:ListSecrets` was called (SIEM-88165), and the wildcard also allows `GetSecretValue` on `claims-api/*`, the secrets used by the claims-api role.
  - `pii`: member-portal resources, plus the `portal-svc` IAM user and its keys, which this role could manage.
  - The analytics bucket (not managed in this repo). APP-2301 confirms doc-service wrote into it.
- **Services / roles:** `doc-service-prod` (role and instance profile), `doc-svc-prod-01`, and through IAM/STS every other principal, including `claims-api-${var.env}` and `portal-svc`.
- **Other groups:**
  - `doc-yaml-rce` (docs-eng) is the entry point. Its unauthenticated `yaml.load(..., Loader=yaml.Loader)` gives code execution on `doc-svc-prod-01` (SIEM-88140 shell, SIEM-88102 egress). This policy turns that into account-wide access (PEN-2024-034). These are separate fixes, and both must land.
  - `member-docs-public-bucket` (platform-eng): same PHI bucket. After this fix the role keeps `s3:GetObject`/`s3:PutObject` on `demo-health-member-docs/*`, which is intended. The bucket's public exposure is fixed separately in that group.
  - `portal-hardcoded-aws-key`: secops should check whether the compromised role touched `portal-svc` keys (CreateAccessKey and similar) during the same window.
  - `claims-search-sqli` / `claims-idor`: no code overlap. Only the shared exposure of claims-api secrets through `secretsmanager:*`.

## Recommended action

**Fix (platform-eng, PR on `fix/doc-service-iam-wildcard`):**
1. Replace the wildcard statement in `aws_iam_role_policy.doc_service` with `Action ["s3:PutObject", "s3:GetObject"]` on `"${aws_s3_bucket.member_docs.arn}/*"` (Sid `MemberDocsObjectReadWrite`). Done in the PR.
2. Add regression test `infra/tests/doc_service_iam.tftest.hcl`. It asserts no wildcard Action or Resource, only Put/Get, scoped to the member-docs bucket objects. Done in the PR. Follow-up: add `terraform test` to the `terraform` CI job, which currently runs only fmt, init, and validate.
3. Before apply, docs-eng should confirm there is no other runtime dependency. The pentest mentions "queue actions", but the repo has no queue usage. If SQS or KMS (SSE-KMS) is needed, add those specific ARNs, not wildcards.
4. Hardening follow-up: require IMDSv2 on `aws_instance.doc_service` (`metadata_options { http_tokens = "required" }`) and add a permissions boundary or SCP that denies `iam:*`/`sts:*` to workload roles.

**Incident response (route to secops, with platform-eng).** SIEM-88165 shows the role credentials being used outside baseline through instance metadata, alongside the `doc-yaml-rce` host compromise:
1. Revoke active `doc-service-prod` sessions now with an inline deny on `aws:TokenIssueTime` earlier than now ("Revoke active sessions"). Don't wait for the Terraform apply.
2. Isolate `doc-svc-prod-01` and rebuild it from a clean AMI after the `doc-yaml-rce` fix ships. Treat the host as compromised.
3. Search CloudTrail for every call by `doc-service-prod` outside `s3:PutObject`/`GetObject` from the first malicious upload (pentest window around 2024-03-31) to now. Prioritize `iam:Create*`/`Attach*`/`Put*`/`Update*`, `sts:AssumeRole`, `secretsmanager:GetSecretValue`, `s3:GetObject`/`ListBucket` on non-doc buckets, `s3:PutBucketPolicy`, and `kms:Decrypt`.
4. Remove any principals, access keys, policies, or trust-policy changes created by that role, and check `portal-svc` and `claims-api-*`.
5. Rotate every Secrets Manager secret that was listed or read, at least `claims-api/*`.
6. Using S3 data events, work out whether PHI objects were read or exfiltrated (`demo-health-member-docs`, plus the 215 KB egress to `203.0.113.77` in SIEM-88102). Start privacy/breach assessment if they were.
7. With docs-eng, review and remove the stray test object in the analytics bucket (APP-2301), and confirm the ingest job's target bucket configuration.

## Status

PR opened
