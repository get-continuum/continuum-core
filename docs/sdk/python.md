# Python SDK

## Install

This repo’s SDK lives under `sdk/src/engram`.

## Resolve intent + contract

```python
from engram import Engram

e = Engram("http://localhost:8000", workspace_id="default", user_token="<user_jwt>")
intent = e.resolve("revenue by campaign", {"team": "marketing"})

if intent.status == "resolved":
    state = e.resolve_metric(intent.resolved_metric.metric_id, {"team": "marketing"})
    print(state.resolved_snapshot)
elif intent.status == "ambiguous":
    print([c.metric_id for c in intent.candidates])
```

