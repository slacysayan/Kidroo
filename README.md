# Kidroo

> Agentic YouTube content pipeline — paste a link, agents handle the rest.ok

Kidroo is a chat-first, agent-native web app that turns a pasted YouTube URL (channel, playlist, or single video) into a fully scheduled upload on one or more of your owned YouTube channels. Five specialized AI agents collaborate in real time — scanning the source, researching context, generating SEO metadata, downloading the asset, and uploading via Composio's OAuth bridge — with every reasoning step, tool call, and status change streaming live into the UI.

**Design principles**

- **Agent activity is the hero.** Every tool call, LLM reasoning step, and progress state streams into the chat. The user watches the operation happen.
- **Resumability is non-negotiable.** Durable workflow engine checkpoints every step. Closing the tab does not lose the job.
- **Free-tier first.** Every service in the stack has a free tier sufficient for a small team running 10–15 channels.

---

## Table of contents

- [What it does](#what-it-does)
- [System canvas](#system-canvas)
- [Tool & tech stack](#tool--tech-stack)
- [API keys required](#api-keys-required)
- [Repository layout](#repository-layout)
- [Phased roadmap](#phased-roadmap)
- [Quick start](#quick-start)
- [Documentation index](#documentation-index)
- [Risks & open items](#risks--open-items)

---

## What it does

```
User pastes:  https://youtube.com/@sourcechannel
           │
           ▼
  Research agent + yt-dlp metadata scan (no download yet)
           │
           ▼
  Inline video-selection card appears in chat
  ┌──────────────────────────────────────────┐
  │ [x] Video 1  │ [x] Video 2  │ [ ] Video 3│
  │ Target: Finance Daily ▼                  │
  │ Schedule: 2/day starting Monday ▼        │
  └──────────────────────────────────────────┘
           │
           ▼
  User sends: "Upload these to Finance Daily, 2/day"
           │
           ▼
  Orchestrator spawns parallel per-video workflows:
  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐
  │ Download  │  │ Research  │  │ Metadata  │  │  Upload   │
  │ (yt-dlp)  │  │ (FC + Exa)│  │ (Groq LLM)│  │ (Composio)│
  └───────────┘  └───────────┘  └───────────┘  └───────────┘
           │
           ▼
  Every step streams to chat in real time via Supabase Realtime
  → Schedule-confirmation card → Job persists, user can close tab
```

---

## System canvas

```
┌───────────────────────── Browser (Next.js 15 @ Vercel) ──────────────────────┐
│  Chat UI  •  Agent log feed  •  Video-selection card  •  Schedule card        │
│  shadcn/ui  •  Tailwind  •  GSAP (primary anim)  •  Framer Motion (shadcn)    │
│  Supabase JS client (Realtime subscription on agent_logs)                     │
└──────────────┬───────────────────────────────────────────────────────────────┘
               │ HTTPS + Realtime WSS (Supabase)
               ▼
┌────────────────────── FastAPI (Python 3.11 @ Koyeb free tier) ───────────────┐
│  POST /jobs        → validates URL, inserts jobs row, enqueues Hatchet run   │
│  GET  /jobs/:id    → returns job + video rows + recent agent_logs             │
│  POST /jobs/:id/select → user submits video selection + channel + schedule   │
│  (No WebSocket — all realtime streaming is done via Supabase Realtime)       │
└──────────────┬───────────────────────────────────────────────────────────────┘
               │ Hatchet Python SDK
               ▼
┌────────────────── Hatchet (self-hosted on Koyeb or Hatchet Cloud free) ──────┐
│  Durable workflow orchestrator — Postgres-backed, checkpointed                │
│  Workflow: scan_channel → fan-out → per-video pipeline                        │
│  Concurrency: max 6 concurrent videos per user                                │
└──────────────┬───────────────────────────────────────────────────────────────┘
               │ spawns CrewAI tasks (Python worker)
               ▼
┌─────────────────────── CrewAI runtime (agents/ package) ─────────────────────┐
│  Orchestrator  →  plans task graph                (Groq LLaMA 3.1 70B)       │
│  Research      →  Firecrawl + Exa tool calls      (Groq)                     │
│  Metadata      →  SEO title/desc/tags JSON        (Groq → Cerebras fallback) │
│  Download      →  yt-dlp subprocess (scan + dl)   (no LLM)                   │
│  Upload        →  Composio YOUTUBE_UPLOAD_VIDEO   (no LLM)                   │
│                                                                              │
│  Every step writes to Supabase agent_logs → broadcasts to browser             │
└──────────────┬───────────────────────────────────────────────────────────────┘
               │
               ├──► Groq / Cerebras     (streaming LLM inference — Groq primary, Cerebras takes over on pre- or mid-stream failure)
               ├──► Firecrawl           (web scraping, 500/mo free)
               ├──► Exa                 (semantic search, free tier)
               ├──► yt-dlp              (local subprocess, no key)
               ├──► Composio            (YouTube OAuth + upload, free)
               └──► Supabase Postgres   (jobs, videos, agent_logs, channels)
                    └── Supabase Realtime (broadcasts agent_logs inserts)
```

A more detailed version with data flow and failure modes lives in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Tool & tech stack

### Frontend

| Layer | Choice | Why |
|---|---|---|
| Framework | **Next.js 15 (App Router)** | React server components, Vercel-native, free deploy |
| Hosting | **Vercel** | Free tier, instant deploys, edge network |
| UI kit | **shadcn/ui** | Owned code (not black-box), composable, startup aesthetic |
| Styling | **Tailwind CSS v4** | Required by shadcn, utility-first |
| Animation (primary) | **GSAP** | Timeline-based agent-log choreography, scroll-triggered transitions |
| Animation (shadcn-native) | **Framer Motion** | Entrance/exit for shadcn components where GSAP would be overkill |
| Typography | **Geist Sans + Geist Mono** | Vercel free font; Mono for agent logs |
| Realtime | **Supabase JS client** | Subscribes to `agent_logs` Postgres changes |
| Icons | **Lucide** | shadcn default |

### Backend

| Layer | Choice | Why |
|---|---|---|
| Server | **FastAPI (Python 3.11)** | Async, CrewAI-native, typed |
| Hosting | **Koyeb free tier** | True always-on free VM (vs Railway's expired free tier) |
| Dependency mgr | **uv** | Fast, lockfile-first, PEP 621 |
| Package mgr (JS) | **pnpm + Turborepo** | Workspace + cached builds |

### Workflow & durability

| Layer | Choice | Why |
|---|---|---|
| Durable orchestrator | **Hatchet** (self-host on Koyeb) | Python-native, Postgres-backed, closest DX to Trigger.dev, fully free to self-host |
| Fallback orchestrator | **Temporal** | If Hatchet proves insufficient — Python SDK, free cloud tier |
| Concurrency | `max_concurrency=6` per user | Configured on the `process_video` Hatchet task |

> Note: the original PRD specified Trigger.dev, which has no Python SDK. Hatchet is the Python-native equivalent and is the canonical choice here.

### Data & auth

| Layer | Choice | Why |
|---|---|---|
| Database | **Supabase Postgres** | Free 500 MB, also powers Realtime |
| Realtime | **Supabase Realtime** | Broadcasts `agent_logs` inserts to the browser |
| Auth | **Supabase Auth (magic link)** | Single-tenant app, 4–5 email allowlist |
| Object storage | **Supabase Storage** | Thumbnails, temp file references (videos stream through Composio's R2) |

### AI & agents

| Layer | Choice | Why |
|---|---|---|
| Agent framework | **CrewAI** | Multi-agent, tool-calling, Python-first |
| LLM (primary) | **Groq — LLaMA 3.1 70B Versatile** | 14,400 req/day free, fastest inference; **always streamed** |
| LLM (fallback) | **Cerebras — LLaMA 3.1 70B** | ~2,000 req/day free; transparent re-routing on pre-stream OR mid-stream failure |
| LLM config | **CrewAI native + shared `stream_complete` wrapper** | No LangChain. Partial tokens flow into `agent_logs` as they arrive, so the browser renders the agent thinking in real time. |

> Note: the original PRD specified LangChain as an abstraction layer. CrewAI already handles this — adding LangChain is redundant.

### External tools

| Tool | Role | Auth |
|---|---|---|
| **Firecrawl** | Scrape source page → clean markdown for LLM context | API key |
| **Exa** | Semantic search — niche trend keywords for metadata | API key |
| **yt-dlp** | Channel/playlist scan (metadata) + video download | No key (Python subprocess) |
| **Composio** | YouTube OAuth bridge + `YOUTUBE_UPLOAD_VIDEO` action | API key + per-channel OAuth |

---

## API keys required

All secrets are loaded from environment variables. See [`.env.example`](.env.example) for the canonical list.

| Env var | Service | Where to get it | Free tier |
|---|---|---|---|
| `GROQ_API_KEY` | Groq (primary LLM) | https://console.groq.com | 14,400 req/day |
| `CEREBRAS_API_KEY` | Cerebras (fallback LLM) | https://cloud.cerebras.ai | ~2,000 req/day |
| `COMPOSIO_API_KEY` | Composio (YouTube OAuth + upload) | https://app.composio.dev | Free |
| `FIRECRAWL_API_KEY` | Firecrawl (web scraping) | https://firecrawl.dev | 500 pages/mo |
| `EXA_API_KEY` | Exa (semantic search) | https://exa.ai | Free tier |
| `SUPABASE_URL` | Supabase (Postgres + Realtime + Auth) | https://supabase.com/dashboard | Free (500 MB DB) |
| `SUPABASE_ANON_KEY` | Supabase client SDK | ↑ | Free |
| `SUPABASE_SERVICE_KEY` | Supabase server SDK | ↑ | Free |
| `HATCHET_CLIENT_TOKEN` | Hatchet (durable workflows) | https://hatchet.run (cloud) or self-host | Free |
| `NEXT_PUBLIC_SUPABASE_URL` | Frontend Supabase URL | = `SUPABASE_URL` | — |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Frontend Supabase anon key | = `SUPABASE_ANON_KEY` | — |
| `NEXT_PUBLIC_API_BASE_URL` | Frontend → backend base URL | Koyeb deploy URL | — |

**YouTube credentials are *not* stored in env.** They are attached per-channel via Composio OAuth using `composio connections create --toolkit YOUTUBE --user-id <app_user_id>` and stored as Composio entity IDs in the `channels` table.

---

## Repository layout

```
Kidroo/
├── README.md                          ← you are here
├── AGENTS.md                          ← entry spec for any coding agent (Cursor/Devin/Claude Code)
├── SKILLS.sh                          ← installs repo deps + registers dev-agent skills
├── .env.example                       ← all env vars with comments
│
├── docs/
│   ├── PRD.md                         ← product requirements (v1.1, corrected)
│   ├── ARCHITECTURE.md                ← full system canvas, data flow, failure modes
│   ├── AGENTS.md                      ← runtime agent specs (5 agents)
│   ├── INTEGRATIONS.md                ← exact API call signatures
│   ├── UI_SPEC.md                     ← shadcn components + GSAP animation spec
│   ├── TECH_STACK.md                  ← every library and why
│   └── ROADMAP.md                     ← phased delivery plan
│
├── .agents/                           ← DEV HARNESS (not shipped to prod)
│   ├── README.md                      ← how to use dev-agent skills
│   └── skills/
│       ├── setup/SKILL.md             ← bootstrap repo, env vars
│       ├── testing/SKILL.md           ← pytest, vitest, e2e commands
│       ├── supabase/SKILL.md          ← migrations, reset db, RLS
│       ├── agents-runtime/SKILL.md    ← conventions for adding a runtime agent
│       ├── frontend/SKILL.md          ← shadcn + tailwind patterns
│       ├── composio/SKILL.md          ← add a new YT channel entity, debug OAuth
│       ├── gsap/SKILL.md              ← agent-log timeline, transition patterns
│       ├── hatchet/SKILL.md           ← write a workflow, test resumability
│       └── security/SKILL.md          ← secrets, RLS, YouTube ToS guardrails
│
├── agents/                            ← RUNTIME (shipped to prod)
│   ├── __init__.py
│   ├── orchestrator/
│   │   ├── agent.py
│   │   ├── prompts.py
│   │   └── skills/
│   ├── research/
│   │   ├── agent.py
│   │   ├── prompts.py
│   │   └── skills/
│   │       ├── firecrawl_scrape.py
│   │       └── exa_search.py
│   ├── metadata/
│   │   ├── agent.py
│   │   └── prompts.py
│   ├── download/
│   │   ├── agent.py
│   │   └── skills/
│   │       └── ytdlp.py
│   └── upload/
│       ├── agent.py
│       └── skills/
│           └── composio_youtube.py
│
├── workflows/                         ← Hatchet durable workflow definitions
│   └── video_pipeline.py
│
├── apps/
│   ├── web/                           ← Next.js 15 frontend
│   └── api/                           ← FastAPI backend
│
├── supabase/
│   └── migrations/
│       └── 001_initial_schema.sql
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── pyproject.toml
└── package.json                       ← pnpm workspace root
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the rationale behind splitting `agents/` (runtime) from `.agents/` (dev harness).

---

## Phased roadmap

The roadmap is phase-based, not day-based. Each phase has an **exit criterion** — a single verifiable outcome that proves the phase is done. Do not start the next phase until the previous phase's exit criterion passes.

### Phase 0 — Foundation

**Scope**
- Repo scaffolding (this PR).
- All documentation finalized: `PRD.md`, `ARCHITECTURE.md`, `AGENTS.md`, `INTEGRATIONS.md`, `UI_SPEC.md`, `TECH_STACK.md`, `ROADMAP.md`.
- `.env.example` complete with every required key.
- `supabase/migrations/001_initial_schema.sql` ready to apply.
- Dev-agent skill tree under `.agents/skills/` complete with `SKILL.md` per skill.
- `SKILLS.sh` installer script.

**Exit criterion:** a new contributor can read `README.md` + `AGENTS.md` and know exactly what to build next with zero clarifying questions.

### Phase 1 — Infra

**Scope**
- Supabase project created, migration applied, Realtime enabled on `agent_logs`.
- Magic-link auth configured with email allowlist.
- Koyeb free VM running a placeholder FastAPI `/health` endpoint.
- Vercel deploying a placeholder Next.js page connected to Supabase auth.
- Hatchet control plane reachable (cloud free tier or self-hosted on Koyeb).
- All API keys provisioned and injected into Koyeb + Vercel env.
- One Composio YouTube entity connected end-to-end; `YOUTUBE_UPLOAD_VIDEO` smoke-tested with a 10-second dummy MP4.

**Exit criterion:** a magic-link user can log into the deployed Vercel app and see their (empty) channel list pulled from Supabase.

### Phase 2 — Agent core

**Scope**
- `agents/` package scaffolded per [`docs/AGENTS.md`](docs/AGENTS.md).
- Groq primary + Cerebras fallback LLM wrapper (no LangChain).
- Each of the 5 agents runnable in isolation via `python -m agents.<name>.agent --input ...`.
- Every agent writes structured rows to `agent_logs` at every step.
- `ytdlp` scan skill returns canonical video-list JSON.
- `firecrawl_scrape` + `exa_search` skills return normalized context blobs.
- `composio_youtube` upload skill successfully uploads + schedules a test video.

**Exit criterion:** running `python -m workflows.video_pipeline --source <url> --channel <entity_id>` end-to-end on a single video produces a scheduled upload on the target channel.

### Phase 3 — Durable orchestration

**Scope**
- `workflows/video_pipeline.py` defines the Hatchet DAG: `scan → fan-out → [download ∥ research → metadata] → upload`.
- Per-user concurrency capped at 6.
- Checkpointing verified: kill the worker mid-run, restart, job resumes from the last completed step.
- Retry policies per step (3× exponential backoff on transient; no retry on auth errors).
- Groq→Cerebras LLM fallback logs `step: "fallback"` row to `agent_logs`.
- Dead-letter handling: jobs that exhaust retries land in a `failed_jobs` view.

**Exit criterion:** submit a 20-video job, kill the Hatchet worker 3 times at random points, all 20 videos still reach `scheduled` state and appear correctly on YouTube.

### Phase 4 — Frontend chat UI

**Scope**
- Chat input, message list, agent-log feed.
- `useAgentLogs(jobId)` Supabase Realtime hook.
- GSAP timeline for agent-log entry animation (slide-up + fade, staggered).
- Inline video-selection card (checkboxes, target-channel select, schedule picker).
- Schedule confirmation card with per-video status badges.
- Sidebar: connected channels, queue summary, quick commands.
- Per-video status-badge state machine: `queued → fetching → downloading → generating → uploading → scheduled | failed`.

**Exit criterion:** end-to-end demo from the browser — paste a channel URL, select videos, assign a target channel + schedule, watch every agent step stream live, see final schedule card. Record the demo.

### Phase 5 — Hardening & production

**Scope**
- Idempotency keys on upload (hash of `source_video_id + target_channel_id`).
- `/tmp` cleanup after every confirmed upload.
- Per-channel YouTube quota tracker.
- Composio OAuth health-check badge in sidebar.
- Per-provider rate-limit tracker (Groq, Firecrawl, Exa) with a kill-switch when budget hits 90%.
- `PIPELINE_ENABLED=false` global kill switch.
- Structured logging with `trace_id` + `span_id` on every `agent_logs` row.
- Nightly E2E smoke test cron (GitHub Actions) that runs a fixture video through the pipeline against a test channel.
- GitHub Actions CI: `ruff` + `mypy` + `pytest` for Python, `biome` + `tsc --noEmit` + `vitest` for JS, Supabase migration linting.

**Exit criterion:** nightly smoke test green for 7 consecutive days.

### Phase 6 — Launch readiness

**Scope**
- Internal user onboarding doc.
- Runbook: "what to do when X fails" for each top-level failure mode.
- Observability dashboard (Supabase SQL views or Grafana on Supabase).
- ToS & copyright risk register (see [Risks](#risks--open-items) below) documented with mitigations.
- Backup/export story for jobs + agent_logs.

**Exit criterion:** hand the app to a non-technical teammate, they successfully schedule 5 videos without help.

---

## Quick start

```bash
# 1. Clone + install
git clone https://github.com/slacysayan/Kidroo.git
cd Kidroo
./SKILLS.sh                          # installs uv + pnpm + system deps, registers dev-agent skills

# 2. Fill in secrets
cp .env.example .env
# edit .env with your keys — every key is documented inline

# 3. Apply Supabase migration
supabase db push                     # or: psql $SUPABASE_DB_URL -f supabase/migrations/001_initial_schema.sql

# 4. Connect your first YouTube channel
composio connections create --toolkit YOUTUBE --user-id finance_daily

# 5. Run backend + frontend
pnpm dev                             # runs apps/web via Turborepo
uv run fastapi dev apps/api/main.py  # runs apps/api

# 6. Run a Hatchet worker in another terminal
uv run python -m workflows.worker
```

---

## Documentation index

| Doc | Purpose |
|---|---|
| [`AGENTS.md`](AGENTS.md) | Root entry spec for any coding agent working on this repo |
| [`docs/PRD.md`](docs/PRD.md) | Product requirements (v1.1, reconciled) |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System canvas, data flow, failure modes |
| [`docs/AGENTS.md`](docs/AGENTS.md) | Runtime agent specs — inputs, outputs, tools, prompts |
| [`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md) | Exact call signatures for Composio, Firecrawl, Exa, yt-dlp, Groq, Cerebras |
| [`docs/UI_SPEC.md`](docs/UI_SPEC.md) | shadcn component inventory + GSAP animation spec |
| [`docs/TECH_STACK.md`](docs/TECH_STACK.md) | Every library, version, and justification |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Phased delivery plan (same content as above, deeper detail) |
| [`.agents/README.md`](.agents/README.md) | How to use dev-agent skills |

---

## Risks & open items

Documented openly so they are not discovered late.

1. **YouTube ToS & Content ID.** The pipeline is capable of uploading third-party content to channels you own. Re-uploading content you do not own or have a license for is a policy violation and will draw Content ID claims, strikes, or channel termination. Users are responsible for ensuring every source video falls under one of: (a) their own content, (b) explicit license, (c) Creative Commons / public domain, or (d) a legally defensible transformative use. The app should not be deployed publicly.

2. **Composio `YOUTUBE_UPLOAD_VIDEO` bug surface.** A known issue ([ComposioHQ/composio#2954](https://github.com/ComposioHQ/composio/issues/2954)) reports cases where video bytes are not transferred from Composio's R2 to YouTube, producing ghost video IDs that auto-delete within ~10 seconds. Phase 2 must include a post-upload verification step (poll `videos.list` on YouTube for the returned ID and confirm `status.uploadStatus == "uploaded"` after ≥60 seconds).

3. **Scheduling via `publishAt`.** YouTube Data API supports `status.publishAt` for scheduled release when `privacyStatus=private`. Composio's upload action exposes `privacyStatus` but `publishAt` support needs confirmation at Phase 2 entry. Fallback: upload as `private`, then call `YOUTUBE_UPDATE_VIDEO` to set `publishAt`.

4. **Groq + Cerebras daily quotas.** Combined ~16,400 LLM req/day. At ~4 LLM calls per video (orchestrator + research + metadata × 2 passes), ceiling is ~4,000 videos/day — plenty for 4–5 users, but add a per-user daily cap at Phase 5 to prevent one user from exhausting the shared budget.

5. **Firecrawl 500 pages/mo.** Scrape results must be cached in Supabase keyed by `sha256(url)` with a 7-day TTL.

6. **Ephemeral `/tmp`.** Koyeb containers are ephemeral and have limited disk. Downloads must be streamed through Composio's presigned-upload flow wherever possible; if local staging is required, bound the concurrent-download count and auto-purge on failure.

7. **Magic-link allowlist.** Supabase auth allows anyone to sign up by default. Enforce the email allowlist in a Supabase RLS policy plus a `before_signup` Edge Function.

---

## License

Private. Internal use only.
