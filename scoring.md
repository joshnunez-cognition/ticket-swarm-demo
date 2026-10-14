# Scoring: ticket-swarm triage run

Scored against `answer_key.json` on the `answer-key` branch.

## Summary

| Metric | Result |
|---|---|
| Tickets in | 40 |
| Groups found vs. expected | 6 / 6 (all six root causes found; every group maps 1:1 to an expected group) |
| Tickets grouped | 31 (expected 32) |
| Noise filtered | 9 marked noise: 8 correct, 1 incorrect (APP-2240). All 8 expected noise tickets were caught, with no false negatives. |
| Decoys caught | 2 / 2: CSP-9120 (public-by-design bucket), APP-2312 (parameterized query, missing index) |
| PRs opened | 5: [#1](https://github.com/joshnunez-cognition/ticket-swarm-demo/pull/1), [#2](https://github.com/joshnunez-cognition/ticket-swarm-demo/pull/2), [#3](https://github.com/joshnunez-cognition/ticket-swarm-demo/pull/3), [#4](https://github.com/joshnunez-cognition/ticket-swarm-demo/pull/4), [#5](https://github.com/joshnunez-cognition/ticket-swarm-demo/pull/5) |
| Work items triaged-only | 1: `portal-hardcoded-aws-key` (exposed credential, routed to portal-eng + secops, no PR) |
| **Ticket-assignment accuracy** | **39 / 40 = 97.5%** |

## Per-group precision / recall

| Our group | Expected group | Tickets (ours / key) | Precision | Recall | Outcome |
|---|---|---|---|---|---|
| `claims-search-sqli` | `sqli-claims-search` | 6 / 6 | 1.00 | 1.00 | [PR #3](https://github.com/joshnunez-cognition/ticket-swarm-demo/pull/3) |
| `claims-idor` | `idor-claims-get` | 5 / 5 | 1.00 | 1.00 | [PR #1](https://github.com/joshnunez-cognition/ticket-swarm-demo/pull/1) |
| `doc-yaml-rce` | `unsafe-yaml-doc-service` | 5 / 6 | 1.00 | 0.83 | [PR #4](https://github.com/joshnunez-cognition/ticket-swarm-demo/pull/4) |
| `doc-service-iam-wildcard` | `iam-wildcard-doc-service` | 5 / 5 | 1.00 | 1.00 | [PR #2](https://github.com/joshnunez-cognition/ticket-swarm-demo/pull/2) |
| `member-docs-public-bucket` | `public-s3-member-docs` | 5 / 5 | 1.00 | 1.00 | [PR #5](https://github.com/joshnunez-cognition/ticket-swarm-demo/pull/5) |
| `portal-hardcoded-aws-key` | `hardcoded-aws-key` | 5 / 5 | 1.00 | 1.00 | [work item](work_items/portal-hardcoded-aws-key.md) |
| Noise | noise | 9 / 8 | 0.89 | 1.00 | n/a |

Micro-averaged over grouped tickets: precision 31/31 = 1.00, recall 31/32 = 0.97.

## Misses

- **APP-2240** ("upload hangs on large YAML manifests"): we marked it noise as a performance issue, but the key puts it in the unsafe-YAML group. The hang comes from the same full `yaml.Loader` call in `parse_manifest` on untrusted input (resource exhaustion), so it belongs with that defect.

## Wall-clock time (UTC)

| Phase | Start | End | Duration |
|---|---|---|---|
| 1. Map (4 parallel sessions) | 18:42:01 | 18:44:42 | 2m 41s |
| 2. Reduce (groups.md, map_results.json) | 18:44:42 | 18:46:16 | 1m 34s |
| 3. Fan out (6 parallel sessions; 5 PRs + 1 work item) | 18:46:16 | 18:52:14 | 5m 58s |
| Waiting for answer key (human gate) | 18:52:14 | 18:53:08 | 0m 54s |
| 4. Score | 18:53:08 | 18:53:37 | 0m 29s |
| **Total (excluding answer-key wait)** | | | **10m 42s** |
| **Total wall clock** | 18:42:01 | 18:53:37 | **11m 36s** |
