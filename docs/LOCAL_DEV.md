# Local development

How to run the full Kidroo stack on `localhost`.

## Stack

| Service | Port | Entrypoint | Purpose |
|---|---|---|---|
| FastAPI | `8000` | `apps/api/main.py` | REST surface — `/jobs`, `/jobs/{id}/start`, `/health` |
| Hatchet worker | — | `workflows.worker` | Runs the `process_video_batch` DAG. Connects to Hatchet Cloud via `HATCHET_CLIENT_TOKEN`. |
| Next.js | `3000` | `apps/web` | Browser UI — login, channel connect, job chat. |
| Supabase | — | managed | Database, auth, realtime. |

## One-time setup

```bash
./SKILLS.sh                        # installs uv, Node 20, pnpm, yt-dlp, ffmpeg
cp .env.example .env               # fill values per `.env.example` comments
cp apps/web/.env.local.example apps/web/.env.local 2>/dev/null || true
uv sync
pnpm install
```

Apply migrations (if you haven't already — this is a one-time step per Supabase project):

```bash
psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/001_initial_schema.sql
psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/002_auth_allowlist.sql
psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/003_jobs_user_default_and_quota_rpc.sql
```

On Supabase free tier the direct `db.<ref>.supabase.co:5432` hostname is **IPv6-only**. Most CI runners and dev VMs are IPv4-only, so use the transaction pooler URL instead — Project Settings → Database → Connection string → **Transaction pooler**. The env var name stays `SUPABASE_DB_URL`.

### Required env keys for `apps/web/.env.local`

```env
NEXT_PUBLIC_SUPABASE_URL=https://<ref>.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Next.js only exposes variables prefixed with `NEXT_PUBLIC_` to the browser. Never put `SUPABASE_SECRET_KEY` here.

## Boot the stack

```bash
./scripts/dev.sh            # boots api + worker + web
./scripts/dev.sh api web    # subset (no worker)
./scripts/dev.sh stop       # kill everything
```

Tail logs (the worker only writes a log file when `HATCHET_CLIENT_TOKEN` is set, so glob your existing files instead of hard-coding the worker name):

```bash
tail -f .logs/api.log .logs/web.log                  # always present
tail -f .logs/worker.log                             # only when worker booted
# or, glob whichever logs exist:
tail -f .logs/*.log
```

Verify:

```bash
curl -fsS http://127.0.0.1:8000/health
# {"status":"ok","pipeline_enabled":false,"version":"0.2.0"}

curl -fsSLI http://127.0.0.1:3000/login | head -1
# HTTP/1.1 200 OK
```

## Safe-by-default kill switch

The backend honors `PIPELINE_ENABLED`. When set to `false` (default in `.env.example`), the upload agent stops short of calling `YOUTUBE_UPLOAD_VIDEO` — every other step runs normally, including downloading and metadata generation, so you can exercise the full DAG locally without publishing videos to a real channel.

To go live on a dev channel:

```env
PIPELINE_ENABLED=true
```

## Common failures

| Symptom | Fix |
|---|---|
| `Cannot find module '@tailwindcss/postcss'` from Next.js | `pnpm --filter web add -D @tailwindcss/postcss` then restart dev server |
| `psql: password authentication failed` | Check `SUPABASE_DB_URL` — Supabase shows `[YOUR-PASSWORD]` as a *placeholder*, not part of the password. No brackets. |
| Worker log stops at `starting runner...` then nothing | Token invalid or wrong gRPC host. Decode the JWT at jwt.io, check the `grpc_broadcast_address` claim matches `HATCHET_CLIENT_HOST_PORT`. |
| `/login` returns 500, error mentions `globals.css` | Tailwind v4 postcss plugin missing — see first row. |
| Web dev server reads wrong `.env` | Next.js only reads `apps/web/.env.local` (not the root `.env`). Duplicate the `NEXT_PUBLIC_*` keys there. |

## Related

- [`docs/DEPLOYMENT.md`](DEPLOYMENT.md) — Railway + Vercel production wiring.
- [`.agents/skills/setup/SKILL.md`](../.agents/skills/setup/SKILL.md) — first-time contributor checklist.
- [`.agents/skills/hatchet/SKILL.md`](../.agents/skills/hatchet/SKILL.md) — worker architecture deep dive.
