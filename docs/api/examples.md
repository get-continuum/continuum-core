# API examples

## Resolve intent (may be ambiguous)

```bash
curl -X POST 'http://localhost:8000/metrics/resolve_intent' \
  -H 'Authorization: Bearer <user_jwt_or_workspace_key>' \
  -H 'Content-Type: application/json' \
  -d '{"query":"revenue","context":{"team":"unknown"}}'
```

## Resolve contract (deterministic)

```bash
curl -X POST 'http://localhost:8000/metrics/revenue/resolve?workspace_id=default' \
  -H 'Authorization: Bearer <user_jwt_or_workspace_key>' \
  -H 'Content-Type: application/json' \
  -d '{"context":{"team":"marketing","use_case":"weekly_performance"}}'
```

