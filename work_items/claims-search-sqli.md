# Work item: `claims-search-sqli`

## Summary

`search_claims()` in `services/claims-api/app/search.py` built its SQL with Python `%` formatting: `"... WHERE member_id = '%s' AND description LIKE '%%%s%%' ..." % (member_id, term)`. It then ran the string with `db().execute(query)` and bound no parameters. The search term `q` comes from `GET /claims/search?q=` (`routes.py:10-12`), so any authenticated caller controls part of the SQL (CWE-89).

Reproduced on `main` with the FastAPI `TestClient` as `token-alice` (member `m-100`):

| Payload (`q`) | Result on `main` |
|---|---|
| `%' OR 1=1 --` | `200`, returned all 5 seed claims, including `m-200` and `m-300` claims |
| `' UNION SELECT 1, name, sql, 4, 5, 6 FROM sqlite_master --` | `200`, returned the `claims` table `CREATE TABLE` statement (schema extraction) |
| `O'Neill` | `500 Internal Server Error` (unterminated string literal) |

Fix: the query now uses `?` placeholders and binds `(member_id, f"%{term}%")`. A quote in `q` is matched as literal text. The `member_id` scope can no longer be dropped. The new regression tests in `services/claims-api/tests/test_search_sqli.py` fail on `main` (3 of 4) and pass with the fix.

## Linked tickets

| Ticket | Source | Title |
|---|---|---|
| SCA-4471 | dependency_scanner | SAST: Possible SQL injection (CWE-89) - 1 finding, HIGH |
| PEN-2024-017 | pentest | Authenticated SQL injection in claims search endpoint |
| PEN-2024-019 | pentest | Verbose database errors returned to client |
| SIEM-88241 | siem_alert | WAF signature match: SQLI_PATTERN_UNION_SELECT (x37) |
| SIEM-88310 | siem_alert | Anomalous query volume - claims-api-prod-01 |
| APP-2291 | app_bug | search box breaks when you type an apostrophe |

## Owning team

- **claims-eng** (`services/claims-api`, `#claims-eng`, claims-eng-oncall@example.com) owns the code fix and the PR.
- Also routed to **secops** (`#secops`, secops-oncall@example.com) for incident response. SIEM-88241 and SIEM-88310 suggest the bug was exploited in production.

## Severity

**Critical (Sev 0):** any authenticated member could read every member's claims and the DB schema (an authz bypass on `data_class: phi`). SIEM-88241 (37 SQLi payloads forwarded to origin, WAF in COUNT mode) and SIEM-88310 (rows-per-query p99 12 -> 4180) suggest this was exploited in prod.

## Blast radius

- **Data:** the `claims` table in `claims-api`. `ownership.yaml` classes it as `data_class: phi`. Exposed columns: `id`, `member_id`, `description` (procedure or visit type), `service_date`, `amount`, `status` for every member. Schema metadata (`sqlite_master`) is also exposed, as PEN-2024-017 says. `sqlite3.execute()` runs one statement only, so stacked `INSERT`/`UPDATE`/`DROP` was not possible through this path. The impact is to confidentiality, not integrity.
- **Services:** `claims-api` (`GET /claims/search`) on `claims-api-prod-01` (`infra/compute.tf`). The member portal's claims search uses this endpoint (APP-2291 asset "member portal -> claims search", `claimsApiUrl` in `member-portal/config/default.json`). The portal's own inbox search (`member-portal/src/messages.js`) is parameterized and not affected. The claims-api IAM role only allows `secretsmanager:GetSecretValue` on `claims-api/*`, and that cannot be reached from SQL. The injection does not extend into AWS.
- **Roles:** any valid bearer token. `member` (`token-alice`, `token-bob`) and `adjuster` tokens can all exploit it. Member scoping was the only control on this endpoint, and the injection removed it.
- **Other groups:**
  - **`claims-idor`** is a separate defect (`get_claim` has no ownership check, `routes.py:15-20`) in the same service, on the same PHI table. Fixing one does not fix the other. Both have to land before claims data is member-scoped. Their exploitation signals stay separate: SIEM-88275 (id enumeration, belongs to `claims-idor`) and SIEM-88310 (bulk rows-per-query, belongs here). The IR review should look at both together, because one actor may have used both paths.
  - No overlap with `doc-yaml-rce`, `doc-service-iam-wildcard`, `member-docs-public-bucket` or `portal-hardcoded-aws-key`.

## Recommended action

Code fix (claims-eng), in the PR from `fix/claims-search-sqli`:

1. Parameterize `search_claims()` (done in the PR) and keep the regression tests for boolean, UNION and apostrophe input.
2. Look for any other `%`/f-string SQL in `claims-api` before closing SCA-4471. On `main`, `search.py` is the only one; `routes.py` already binds `?`.
3. PEN-2024-019: the 500 trigger is gone with this fix. On `main` the default FastAPI handler returns a generic `Internal Server Error`, so the verbose-message part did not reproduce. Confirm that prod does not run with debug or a custom handler that returns DB error text. Close the ticket if it doesn't.
4. APP-2291: verify `O'Neill` in portal claims search after deploy, then close.

Incident response (secops, with claims-eng):

1. Treat SIEM-88241 + SIEM-88310 as a suspected PHI exfiltration incident. Open an IR ticket and keep ALB/WAF and application logs for `claims-api-prod-01` from the alert windows (2024-04-03 14:22Z +/- 11 min; 2024-04-04 02:07Z 5-min window) and from earlier.
2. Find the token or member behind `src 198.51.100.42` (`python-requests/2.31`) and the caller in SIEM-88310. Revoke or rotate those tokens and block the source IP.
3. Using the logged `q` values and response sizes, work out which members' claims were returned. Hand that to privacy/compliance for the HIPAA breach-notification assessment.
4. Move the AWS SQLi managed rule on `alb/claims-api-prod` from `COUNT` to `BLOCK` (platform-eng owns the ALB/WAF config) as defense in depth, once the fix is deployed.
5. Correlate with `claims-idor` signals (SIEM-88275) to see whether the same actor used both paths.

## Status

PR opened (`fix/claims-search-sqli` -> `main`).
