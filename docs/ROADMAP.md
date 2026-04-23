# Roadmap

Phase-based, not day-based. Each phase has a single **exit criterion** that must pass before starting the next phase.

---

## Phase 0 — Foundation (this PR)

### Deliverables

- Repo scaffolded: `/docs`, `/agents`, `/.agents`, `/apps`, `/workflows`, `/supabase`, `/tests`.
- Documentation locked: `README.md`, `AGENTS.md`, `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/AGENTS.md`, `docs/INTEGRATIONS.md`, `docs/UI_SPEC.md`, `docs/TECH_STACK.md`, this `ROADMAP.md`.
- `.env.example` complete with every required key and inline docs.
- `SKILLS.sh` installer ready.
- Dev-harness skills: `setup`, `testing`, `supabase`, `agents-runtime`, `frontend`, `composio`, `gsap`, `hatchet`, `security` — each with a `SKILL.md`.
- `supabase/migrations/001_initial_schema.sql` ready to apply.

### Exit criterion

A new contributor reads `README.md` + `AGENTS.md` and can identify the next file to work on without asking.

---

## Phase 1 — Infra

### Deliverables

- Supabase project provisioned; migration applied.
- Supabase Realtime enabled on `agent_logs`.
- Supabase Auth magic link configured with an email allowlist (enforced at RLS + `before_signup` Edge Function).
- Koyeb free VM running a placeholder FastAPI `/health` endpoint.
- Vercel deploying a placeholder Next.js page.
- Hatchet control plane reachable (cloud or self-host).
- All API keys provisioned and loaded into Koyeb + Vercel secrets.
- One Composio YouTube entity connected end-to-end.
- `YOUTUBE_UPLOAD_VIDEO` smoke-tested with a 10-second dummy MP4.

### Exit criterion

A Supabase Auth (email+password / magic link / Google OAuth) user logs into the deployed Vercel app and sees an empty channel list pulled from Supabase.

---

## Phase 2 — Agent core

### Deliverables

- `agents/` package scaffolded per `docs/AGENTS.md`.
- `agents/lib/llm.py` — Groq primary + Cerebras fallback wrapper.
- `agents/lib/logging.py` — structured logger that writes to `agent_logs`.
- All 5 agents runnable in isolation: `uv run python -m agents.<name>.agent --input …`.
- `firecrawl_scrape` skill — with Supabase-backed cache keyed by URL hash.
- `exa_search` skill.
- `ytdlp` skill — scan + download + progress streaming.
- `composio_youtube` skill — upload + post-upload verification (`fileDetails.fileSize` poll) + `publishAt` via `YOUTUBE_UPDATE_VIDEO`.
- Composio `publishAt` direct-param support probed; decision recorded in `docs/INTEGRATIONS.md`.

### Exit criterion

Running `uv run python -m workflows.video_pipeline --source <url> --channel <entity_id>` end-to-end for a single video produces a scheduled upload on the target channel, verified via `YOUTUBE_GET_VIDEO`.

---

## Phase 3 — Durable orchestration

### Deliverables

- `workflows/video_pipeline.py`:
  - `process_video_batch` — fan-out per video, bounded by `user_id` concurrency group (`max_runs=6`).
  - `process_single_video` — concurrent download + research → metadata → upload.
- Retry policies per step (3× exponential backoff on transient; no retry on auth errors).
- LLM fallback logs `step='fallback'` rows.
- Dead-letter: jobs exhausting retries surface in a `failed_jobs` view.
- Idempotency key on upload = `sha256(source_video_id + channel_entity_id)`.

### Exit criterion

Submit a 20-video job; kill the Hatchet worker 3 times at random points; all 20 videos still reach `scheduled` state and appear on YouTube.

---

## Phase 4 — Frontend chat UI

### Deliverables

- Chat input + message list.
- `useAgentLogs(jobId)` — Supabase Realtime subscription hook.
- Agent-log rail with GSAP slide-up animation and color-coded pills.
- Inline video-selection card.
- Schedule-confirmation card with per-video status badges.
- Sidebar: channels (with OAuth health dots), queue summary, quick commands (`⌘K`).
- `prefers-reduced-motion` handling.

### Exit criterion

Recorded demo: user pastes a channel URL, selects 5 videos, submits, watches agent steps stream in real time, sees final schedule card. Demo attached to the PR.

---

## Phase 5 — Hardening

### Deliverables

- `/tmp` cleanup job after every confirmed upload.
- Per-channel YouTube quota tracker in `channel_quota` table.
- Per-provider rate-limit tracker (Groq, Firecrawl, Exa) with 90 %-of-budget warning and 100 %-kill-switch.
- Global `PIPELINE_ENABLED=false` kill switch honored at `POST /jobs`.
- Structured logs with `trace_id` + `span_id` on every `agent_logs` row.
- Nightly E2E smoke test (GitHub Actions) against a fixture video + test channel; Slack/Discord notification on fail.
- CI: `ruff` + `mypy --strict` + `pytest` for Python, `biome` + `tsc --noEmit` + `vitest` for JS, Supabase migration linting.
- Pre-commit hooks: `ruff format`, `ruff check --fix`, `biome check --apply`, `gitleaks`, `pytest --collect-only` (fast).

### Exit criterion

Nightly smoke test green for 7 consecutive days.

---

## Phase 6 — Launch readiness

### Deliverables

- Internal onboarding doc: `docs/ONBOARDING.md`.
- Runbook: `docs/RUNBOOK.md` — one section per top-level failure mode.
- Observability: Supabase SQL views for job throughput, LLM usage, upload success rate.
- ToS + copyright risk register with mitigations signed off.
- Backup/export story for `jobs` + `agent_logs` (Supabase scheduled pg_dump to Storage bucket).
- Optional: Turnkey provisioning script (`scripts/bootstrap.sh`) that creates Supabase project + Koyeb service + Vercel project in one shot.

### Exit criterion

A non-technical teammate onboards in <15 minutes and successfully schedules 5 videos end-to-end without help.
