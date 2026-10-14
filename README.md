# ticket-swarm-demo

Fictional "Demo Health" platform used to demo security-ticket triage with a swarm of Devin sessions.
Everything here is synthetic: no real members, customers, credentials or infrastructure.

| Path | What | Owner |
|---|---|---|
| `services/claims-api` | FastAPI claims lookup and search | claims-eng |
| `services/doc-service` | Python document upload/ingest | docs-eng |
| `services/member-portal` | Node/Express member web portal | portal-eng |
| `infra/` | Terraform for AWS (S3, IAM, EC2) | platform-eng |

`tickets/tickets.json` is a batch of open security tickets exported from five tools.

## Running tests

```bash
(cd services/claims-api && pip install -r requirements.txt && pytest -q)
(cd services/doc-service && pip install -r requirements.txt && pytest -q)
(cd services/member-portal && npm ci && npm test)
```
