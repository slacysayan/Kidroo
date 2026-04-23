# Deployment

Hosting is **provider-pluggable**. The repo ships:

- [`Procfile`](../Procfile) — declares two processes: `api` (FastAPI) and `worker` (Hatchet).
- [`nixpacks.toml`](../nixpacks.toml) — Nixpacks build plan (Python 3.12 + ffmpeg + `uv sync`).
- [`railway.json`](../railway.json) — Railway-specific deploy hints.

Any Nixpacks-compatible PaaS (Railway, Render, Fly's buildpack mode, …) will consume the same files. Swapping accounts or providers is a **config change only** — there is no code in the repo that assumes Railway.

## Railway (current target)

Two services in the same project, both pointed at this repo:

| Service | Start command | Env extras |
|---|---|---|
| `kidroo-api` | `uv run uvicorn apps.api.main:app --host 0.0.0.0 --port $PORT` | `PORT` is auto-injected by Railway |
| `kidroo-worker` | `uv run python -m workflows.worker` | — |

Both services share the same env-var set (Groq, Cerebras, Tavily, Firecrawl, Exa, Composio, Supabase, Hatchet). The worker does not need `PORT`.

### Switching Railway accounts

1. Create the new Railway project.
2. Run `railway link` (or paste the project token in the UI) from the same repo clone.
3. Copy the env vars over (Railway dashboard → service → Variables → "Copy from another project").
4. Deploy. No code change is required.

### Switching provider (Fly.io / Render / …)

1. Keep `Procfile` + `nixpacks.toml`.
2. On Fly.io: `fly launch --no-deploy`, then edit the generated `fly.toml` to use two processes (`api` + `worker`) that reference the same `Procfile` commands. Deploy with `fly deploy`.
3. On Render: create two services — one **Web Service** pointing at the `api` Procfile entry, one **Background Worker** pointing at the `worker` entry.
4. Supply the same env vars.

## Vercel (frontend)

The `apps/web/` Next.js app deploys on Vercel Hobby. Root directory is `apps/web`. Required env vars:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` (or `NEXT_PUBLIC_SUPABASE_ANON_KEY`)
- `NEXT_PUBLIC_API_BASE_URL` — the public URL of the Railway API service.

## Hatchet

Primary: **Hatchet Cloud** free tier (already configured via `HATCHET_CLIENT_TOKEN` + `HATCHET_CLIENT_HOST_PORT=engine.hatchet-tools.com:7077`).

Fallback: self-host on Railway or any Docker host using the upstream `hatchet-dev/hatchet` compose file. Swap the two env vars above to point at the self-hosted control plane.
