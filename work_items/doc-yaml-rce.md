# Work item: `doc-yaml-rce`

## Summary

`parse_manifest()` in `services/doc-service/doc_service/upload.py:15` parsed the body of the unauthenticated `POST /upload` request (`app.py:11-15`) with `yaml.load(raw, Loader=yaml.Loader)`. The full Loader builds arbitrary Python objects, so a manifest containing `!!python/object/apply:os.system [...]` runs commands as the doc-service process on doc-svc-prod-01 (CWE-502). The pinned `PyYAML==5.3.1` (`requirements.txt:1`) is also affected by CVE-2020-14343, the same bug class in the same call.

**Reproduced on `main` (observed):** a regression test posting `!!python/object/apply:os.system ['touch <marker>']` to `/upload`, and passing the same tag inside an otherwise valid manifest to `parse_manifest()`, created the marker file. Both tests failed on unpatched code (`2 failed, 4 passed`). That is command execution through the request body.

**Fix (this PR):** `yaml.safe_load()` replaces the full Loader, YAML errors map to `UploadError` (HTTP 400), and PyYAML is bumped `5.3.1 -> 6.0.1`. 5.4.1 is the first fixed release, but its sdist no longer builds with Cython 3. 6.0.1 ships wheels for the CI Python (3.8) and for 3.10. After the fix all 6 doc-service tests pass, and the marker file is not created.

## Linked tickets

| ID | Source | Title |
|---|---|---|
| SCA-4403 | dependency_scanner | SAST: Unsafe YAML deserialization (CWE-502) |
| SCA-4402 | dependency_scanner | PyYAML 5.3.1 - CVE-2020-14343 (CRITICAL, 9.8) |
| PEN-2024-023 | pentest | Remote code execution via config/manifest upload |
| SIEM-88140 | siem_alert | Shell spawned by application process (doc-svc-prod-01) |
| SIEM-88102 | siem_alert | Unexpected outbound connection from doc-svc-prod-01 |

## Owning team

- **docs-eng** owns `services/doc-service` (`ownership.yaml`; `#docs-eng`, docs-eng-oncall@example.com). They own the code fix and this PR.
- Routed to **secops** (`#secops`, secops-oncall@example.com) for incident response on doc-svc-prod-01, because SIEM-88140 and SIEM-88102 show signs of exploitation.
- FYI **platform-eng** (`#platform-eng`): the host's IAM role is the amplifier. That fix is tracked separately in group `doc-service-iam-wildcard`.

## Severity

**Critical (Sev 0).** This is unauthenticated remote code execution on a PHI-handling production service. The pentest confirmed it (PEN-2024-023), and SIEM shows a shell spawned by the app process plus first-seen egress from the same host. There is no workaround.

## Blast radius

- **Data:** doc-service is `data_class: phi` (`ownership.yaml`). The process writes member documents to `demo-health-member-docs` (`storage.py`, `DOCS_BUCKET`), which is tagged `DataClass=phi`. Code execution gives direct read/write access to every member document the service handles.
- **Host:** full compromise of doc-svc-prod-01 (`infra/compute.tf` `aws_instance.doc_service`), including environment variables and anything else on the box.
- **Role:** the instance profile `aws_iam_instance_profile.doc_service` carries role `doc-service-prod`. Its inline policy `doc-service-access` is `Action "*"` / `Resource "*"` (group **`doc-service-iam-wildcard`**). Through instance metadata, RCE becomes **AWS account-wide admin**: IAM principal creation, every S3 bucket, and Secrets Manager (including the `claims-api/*` secrets, which are **claims-api / PHI**). SIEM-88165 in that group (`iam:ListRoles`, `s3:ListAllMyBuckets`, `secretsmanager:ListSecrets` from `doc-service-prod`) is consistent with this chain being used (hypothesis; correlate timestamps with SIEM-88140/88102).
- **Other groups touched:**
  - `doc-service-iam-wildcard`: the amplifier, described above. This fix removes the entry point. The IaC fix removes the escalation. Both are needed.
  - `member-docs-public-bucket`: the same PHI bucket that this process writes to. It is already world-readable through a separate defect.
  - `portal-hardcoded-aws-key`: no direct link. The wildcard role could still be used to inspect or abuse other IAM users, such as `portal-svc`.
- **Not in scope:** APP-2240 (upload hangs on large manifests) touches the same line, but it is a performance issue. `safe_load` is also pure-Python and does not change that.

## Recommended action

**Code (this PR, docs-eng):**
1. Merge the `fix/doc-yaml-rce` PR: `yaml.safe_load`, map YAML errors to 400, pin `PyYAML==6.0.1`, and add regression tests that a `!!python/object/apply` manifest is rejected and not executed.
2. Deploy to doc-svc-prod-01 quickly. Until then, consider blocking `!!python` in `/upload` bodies at the WAF/proxy as a stopgap.

**Incident response (secops + docs-eng). The SIEM tickets indicate possible exploitation:**
1. Treat doc-svc-prod-01 as compromised. Snapshot its disk and memory for forensics, then isolate it (restrict egress to the package mirror) before rebuilding from a clean AMI with the patched build.
2. Rotate the `doc-service-prod` role's credentials. Revoke active sessions by adding an `aws:TokenIssueTime` deny on the role, and rotate any secrets present on the host or in its environment.
3. Review CloudTrail for `doc-service-prod` from 2024-03-25 (first scanner finding) to now. Look for IAM principal and access-key creation, `secretsmanager:GetSecretValue`, S3 reads and writes outside `demo-health-member-docs`, and new roles or policies. Correlate with SIEM-88165.
4. Investigate the 215 KB egress to `203.0.113.77:443` (SIEM-88102, 2024-03-31T21:55Z) and the `/bin/sh -c id` spawn (SIEM-88140, 2024-04-01T03:14Z). Rule out the pentest window first (PEN-2024-023 is dated 2024-03-30), and pull `/upload` request logs around both timestamps.
5. If CloudTrail or S3 data events show PHI was accessed or exfiltrated, start the breach assessment and notification process.
6. platform-eng lands the `doc-service-iam-wildcard` scope-down. Without it, any future RCE on this host is account-wide.

## Status

PR opened
