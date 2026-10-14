# Work item: `claims-idor`

## Summary

`GET /claims/{claim_id}` in `claims-api` (`services/claims-api/app/routes.py`, `get_claim`) loaded a claim by its id alone (`SELECT * FROM claims WHERE id = ?`) and returned it. The authenticated principal from `Depends(current_user)` was never compared with `row["member_id"]` and no role was checked, so any member token could read any member's claim (CWE-639, IDOR). Claim ids are small sequential integers (1001-1005 in `db.py`), so the whole table can be enumerated.

Reproduced on `main`: `token-alice` (m-100), `token-bob` (m-200) and `token-adjuster` each got `200` for all five seed claims 1001-1005. The new regression tests (`tests/test_claim_authz.py`) fail on `main` (7 failed, 1 passed) and pass with the fix. Full claims-api suite: 13 passed.

Fix (in this PR): `get_claim` now returns the claim only if the caller owns it (`row["member_id"] == user["user_id"]`) or has a staff role allowed to read all claims (`adjuster`). Otherwise it returns the same `404 claim not found` as a missing id, so ids cannot be probed for existence.

## Linked tickets

| Ticket | Source | Title |
|---|---|---|
| PEN-2024-021 | pentest | Insecure direct object reference - any claim readable by any member |
| SCA-4480 | dependency_scanner | SAST: Route handler with no authorization check (CWE-639) |
| SIEM-88275 | siem_alert | Sequential resource enumeration detected |
| PEN-2024-026 | pentest | Claim identifiers are predictable |
| APP-2305 | app_bug | member saw someone else's claim |

## Owning team

- **claims-eng** (`services/claims-api`, `#claims-eng`, claims-eng-oncall@example.com) owns the code fix and reviews this PR.
- Routed to **secops** (`#secops`, secops-oncall@example.com) for incident response: SIEM-88275 shows the defect was exploited in production.

## Severity

**Critical (Sev 0):** authorization bypass that exposes every member's PHI claim records to any authenticated member, with confirmed production exploitation (598 distinct claims read by one member session in SIEM-88275).

## Blast radius

- **Data:** `claims` table in `claims-api`, `data_class: phi` (`ownership.yaml`). Exposed fields per row: `id`, `member_id`, `description` (service/procedure), `service_date`, `amount`, `status`. Every member's claims were readable.
- **Service:** `claims-api` only (`claims-api-prod-01`, behind `alb/claims-api-prod`). The portal has no claim-detail route of its own. Claim detail is served by `claims-api`, which is how APP-2305 surfaced through the member portal.
- **Roles:** any `member` token could read any claim. `adjuster` access to all claims is intended and is kept.
- **Confirmed exposure:** SIEM-88275, principal `token-***bob` (m-200): 612 distinct ids, 598 `200`s in 9 minutes on `/claims/{id}`. APP-2305 is a second member who saw another member's claim. Both are potential HIPAA breach events.
- **Other groups:**
  - `claims-search-sqli` is in the same service and also leaks cross-member claims, through `/claims/search` (`search.py`). This fix does **not** close that path. Both fixes are needed before claims-api is safe. Bulk row volume (SIEM-88310) belongs to that group, not this one.
  - `doc-yaml-rce`, `doc-service-iam-wildcard`, `member-docs-public-bucket` and `portal-hardcoded-aws-key` have no code or data path in common with this defect.

## Recommended action

1. **claims-eng:** review and merge this PR (ownership/role check in `get_claim`, plus a regression test). Deploy to `claims-api-prod` as an emergency change.
2. **claims-eng (follow-up, PEN-2024-026):** for defense in depth, replace sequential integer claim ids in the external API with non-guessable ids (e.g. UUIDv4 or an opaque public id). Track separately because it changes the schema and API contract. The authorization check is what fixes the vulnerability.
3. **claims-eng:** add a per-principal rate limit or alert on 404 bursts against `/claims/{id}`, so enumeration attempts are still visible after the fix.
4. **secops (incident response):**
   1. Pull `alb/claims-api-prod` access logs for `/claims/{id}` from the earliest retained date. Find every principal that read a claim whose `member_id` is not its own, starting with `token-***bob` / m-200 (SIEM-88275) and the APP-2305 caller.
   2. Build the list of affected members and claim records from those logs.
   3. Revoke or rotate the sessions/tokens involved. Investigate whether account m-200 is compromised or abusive.
   4. With privacy/compliance, run the HIPAA breach-risk assessment and member notification process for the exposed PHI.
   5. Close APP-2305 with the member support team once the fix is deployed.

## Status

PR opened
