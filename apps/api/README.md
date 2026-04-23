# `apps/api` — Kidroo backend

FastAPI (Python 3.12+) — stateless REST. Realtime fanout happens via Supabase Realtime, not here.

## Run

```bash
# From repo root
uv run fastapi dev apps/api/main.py    # dev server on :8000

# Prod (Railway / Fly / Render / any PaaS — same command, driven by Procfile.api)
uv run uvicorn apps.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

## Endpoints (Phase 1)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | no | Liveness + kill-switch state |
| GET | `/auth/me` | yes | Echo the authenticated Supabase user |
| POST | `/jobs` | yes | Enqueue a job on Hatchet _(501 until Phase 3)_ |

## Auth

The client sends `Authorization: Bearer <supabase JWT>`. Phase 5 verifies the signature against `SUPABASE_URL + /auth/v1/.well-known/jwks.json`.

## Config

All env vars are pulled via `agents.lib.config.get_settings()` — typed, cached, validated at startup. Missing keys fail loudly with a Pydantic error.
