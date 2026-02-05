# Quickstart

## Run locally

Install deps:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run API:

```bash
uvicorn app.main:app --reload
```

## Auth (MVP)

By default, auth is optional for local dev. For production, set:

- `ENGRAM_AUTH_REQUIRED=1`
- `ENGRAM_JWT_SECRET=<strong secret>`
- `ENGRAM_KEY_HASH_SECRET=<strong secret>`

### Create a workspace + workspace key

```bash
curl -X POST http://localhost:8000/auth/workspaces \\
  -H 'Content-Type: application/json' \\
  -d '{"name":"Acme"}'
```

```bash
curl -X POST http://localhost:8000/auth/workspaces/<workspace_id>/keys \\
  -H 'Content-Type: application/json' \\
  -d '{"env":"test"}'
```

### Mint a user token (runtime)

```bash
curl -X POST http://localhost:8000/auth/token \\
  -H 'Authorization: Bearer <wk_test_...>' \\
  -H 'Content-Type: application/json' \\
  -d '{"user_id":"u_123","roles":["marketing"],"scopes":["resolve:read"]}'
```

## SDK (Python)

```python
from engram import Engram, MintTokenRequest

e = Engram("http://localhost:8000", workspace_id="default", workspace_key="wk_test_...")
tok = e.mint_user_token(MintTokenRequest(user_id="u_123", roles=["marketing"], scopes=["resolve:read"]))
e.set_user_token(tok.token)

intent = e.resolve("revenue by campaign", {"team": "marketing"})
print(intent)

state = e.resolve_metric(intent.resolved_metric.metric_id, {"team": "marketing"})
print(state.resolved_snapshot)
```

