# Auth + Tenancy (Production-ready MVP)

This page answers **“how do I run Continuum safely in production?”** without turning into an infra whitepaper.

## Tenant isolation model

- Every object is scoped to a `workspace_id`.
- API derives `workspace_id` from auth (not caller input) when `ENGRAM_AUTH_REQUIRED=1`.
- No cross-workspace references are allowed by design.

## Two auth channels

### 1) Workspace API key (required for admin)

- **Who uses it**: customer backend/server (never the browser)
- **What it’s for**: ingestion/admin actions; server-side resolve acting on behalf of users
- **Format**: `wk_live_<key_id>.<secret>`
- **Storage**: server stores a **hash** only

### 2) User token (recommended for runtime)

- **Who uses it**: per end-user (Slack/chat/web app)
- **What it’s for**: identity-aware resolution, auditability, policy enforcement
- **Phase 1**: Continuum-signed JWT (short-lived)
- Includes: `workspace_id`, `sub`/`user_id`, `roles`, `scopes`, optional `agent_id`, `surface`

## Endpoint auth matrix

| API surface | Auth | Why |
|---|---|---|
| Ingest / Admin writes (metrics, aliases, events, overlays) | Workspace key | High privilege |
| Resolve intent (`POST /metrics/resolve_intent`) | User token preferred (or workspace key) | Least privilege + audit |
| Resolve contract (`POST /metrics/{metric_id}/resolve`) | User token or workspace key | Deterministic execution |
| WhoAmI (`GET /auth/whoami`) | User token or workspace key | Safe UX |

## Key management

- Workspace keys are **long-lived** and **rotatable**
- User tokens are **short-lived** (5–60 min) and should be minted server-side

## Audit + observability

Every resolve should be attributable to:

- `workspace_id`
- `user_id`
- `agent_id` (optional)
- `surface` (slack/web/api)
- input hash (optional)
- chosen identity + confidence

## What is stored vs not stored

Stored:

- semantic objects (metrics, events, overlays, aliases)
- usage/audit events (when enabled)

Not stored by default:

- raw conversations/transcripts

