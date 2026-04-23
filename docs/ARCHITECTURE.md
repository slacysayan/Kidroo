# Architecture

## System canvas

```
┌─────────────────────────────── USER BROWSER ────────────────────────────────────┐
│                                                                                  │
│   Next.js 15 (App Router) @ Vercel                                              │
│   ┌─────────────────────┐   ┌──────────────────────┐   ┌──────────────────┐     │
│   │  Sidebar            │   │  Chat feed            │   │  Agent-log rail  │     │
│   │  - Channels         │   │  - Messages           │   │  - Streaming     │     │
│   │  - Queue summary    │   │  - Video-select card  │   │  - GSAP timeline │     │
│   └─────────────────────┘   └──────────────────────┘   └──────────────────┘     │
│                                                                                  │
│   shadcn/ui + Tailwind + GSAP + Framer Motion + Geist                            │
│   Supabase JS client — Realtime subscription on `agent_logs`                     │
│                                                                                  │
└───────────────┬──────────────────────────────────────────────┬──────────────────┘
                │ HTTPS (REST)                                 │ WSS (Realtime)
                ▼                                              ▼
┌──────────────────────────────────┐          ┌──────────────────────────────────┐
│     FastAPI @ Koyeb (free)       │          │  Supabase Realtime (WSS)         │
│                                  │          │  - Broadcasts agent_logs INSERT   │
│  POST /jobs                      │          │  - Broadcasts jobs UPDATE         │
│  GET  /jobs/:id                  │          │  - Broadcasts videos UPDATE       │
│  POST /jobs/:id/select           │          └──────────────────────────────────┘
│  POST /channels/connect          │                            ▲
│                                  │                            │
│  (No WebSocket — streaming is    │                            │
│   done via Supabase Realtime     │                            │
│   from the browser directly.)    │                            │
└─────────┬────────────────────────┘                            │
          │ Hatchet Python SDK                                  │
          ▼                                                     │
┌──────────────────────────────────────────────┐                │
│  Hatchet control plane                       │                │
│  (Hatchet Cloud free OR self-host on Koyeb)  │                │
│                                              │                │
│  - Durable workflow engine                   │                │
│  - Postgres-backed checkpoints               │                │
│  - Fan-out / concurrency groups              │                │
└─────────┬────────────────────────────────────┘                │
          │ dispatches tasks                                    │
          ▼                                                     │
┌────────────────────────────────────────────────────────────┐  │
│  Hatchet worker (Python process on Koyeb)                  │  │
│                                                            │  │
│  workflows/video_pipeline.py                               │  │
│     └── process_video_batch                                │  │
│            └── process_single_video (×N, max 6 concurrent) │  │
│                    ├── download_video()                    │  │
│                    ├── research_video()                    │  │
│                    ├── generate_metadata()                 │  │
│                    └── upload_video()                      │  │
│                                                            │  │
│  Each step delegates to a CrewAI agent in agents/*          │  │
└─────────┬──────────────────────────────────────────────────┘  │
          │                                                     │
          │ agents/lib/logging writes ───────────────────────►  │
          │ every step to Supabase agent_logs ─────────────────►┘
          │
          ├─► agents/orchestrator/  (Groq — plans task graph)
          ├─► agents/research/      (Groq + Firecrawl + Exa)
          ├─► agents/metadata/      (Groq — SEO JSON)
          ├─► agents/download/      (yt-dlp subprocess)
          └─► agents/upload/        (Composio YOUTUBE_UPLOAD_VIDEO)
                                         │
                                         ▼
                        ┌────────────────────────────────────┐
                        │  Composio managed YouTube OAuth    │
                        │  - One entity per channel          │
                        │  - Handles token refresh           │
                        │  - Routes upload to correct channel│
                        └────────────────────────────────────┘
                                         │
                                         ▼
                        ┌────────────────────────────────────┐
                        │  YouTube Data API v3               │
                        │  - videos.insert (upload)          │
                        │  - videos.update (publishAt)       │
                        └────────────────────────────────────┘

┌──────────────────── Supabase Postgres (free tier) ────────────────────┐
│  Tables:                                                              │
│    auth.users            (Supabase Auth — magic link)                 │
│    public.channels       (Composio entity IDs, per user)              │
│    public.jobs           (one row per user submission)                │
│    public.videos         (one row per selected video)                 │
│    public.agent_logs     (append-only stream; Realtime enabled)       │
│  RLS: every table filtered by auth.uid() = user_id                    │
└───────────────────────────────────────────────────────────────────────┘
```

## Data flow — URL paste → scheduled video

1. **Submit.** User pastes URL in chat. Browser calls `POST /jobs` on FastAPI with `{source_url}`.
2. **Validate + enqueue.** FastAPI classifies the URL (channel / playlist / video), inserts a `jobs` row (`status='pending'`), and dispatches a Hatchet workflow run `scan_source`.
3. **Scan.** The `scan_source` workflow runs `yt-dlp --dump-json --flat-playlist` → returns video metadata without downloading. Rows inserted into `videos` (`status='queued'`).
4. **Select.** Frontend, listening on `videos` INSERT via Realtime, renders the inline selection card. User picks videos, target channel, and schedule, then `POST /jobs/:id/select`.
5. **Fan-out.** FastAPI updates the `jobs` row with the selection and dispatches `process_video_batch`. The batch workflow spawns one `process_single_video` child per video, bounded by concurrency group `user_id` with `max_concurrent=6`.
6. **Per-video pipeline** (concurrent):
   - `download_video()` shells out to yt-dlp → `/tmp/{job_id}/{video_id}.mp4`. Progress is parsed from stdout and written to `agent_logs` every 5 %.
   - `research_video()` calls Firecrawl + Exa, produces a context blob cached in Supabase.
   - `generate_metadata()` passes context + video to Groq (fallback Cerebras) → JSON metadata.
   - `upload_video()` fires once download + metadata are both complete. Calls Composio `YOUTUBE_UPLOAD_VIDEO` with `privacyStatus='private'` and `publishAt` set to the scheduled slot.
7. **Verify.** After upload, poll `YOUTUBE_GET_VIDEO` until `status.uploadStatus='uploaded'` (mitigates Composio bug #2954). Update `videos.status='scheduled'`.
8. **Log.** Every step writes an `agent_logs` row. Realtime broadcasts to the browser, which renders the line in the agent-log rail with a GSAP slide-up animation.
9. **Cleanup.** `/tmp/{job_id}/{video_id}.mp4` is removed immediately after upload verification.

## Failure modes & recovery

| Layer | Failure | Recovery |
|---|---|---|
| Hatchet worker | Process killed | Control plane re-dispatches from last checkpoint. |
| LLM provider | 429 / 5xx | Automatic failover Groq → Cerebras; `step='fallback'` log row. |
| Firecrawl | 429 / 5xx | Hatchet retry with exponential backoff. Cache hit suppresses retry. |
| yt-dlp | Non-zero exit | Retry once with `--no-check-certificate`; else mark `failed`. |
| Composio upload | Error or ghost upload | Compensating delete + retry up to 3×; then `failed`. |
| Supabase | Realtime disconnect | JS client auto-reconnects; logs are backfilled on reconnect. |
| Koyeb | Container restart | Hatchet resumes; FastAPI is stateless. |
| User | Closes tab | Realtime subscription re-established on next load; state is server-side. |

## Why `agents/` (runtime) vs `.agents/` (dev harness)

Two trees by design:

- `agents/` contains **importable Python packages** that ship in the Docker image and run in production. They define runtime behavior.
- `.agents/` contains **markdown-only** skill files consumed by coding agents (Devin, Cursor, etc.). They never ship and never import.

Separation prevents (a) accidental circular deps from a runtime import dragging in dev-only code, (b) dev-tool files inflating the production image, and (c) coding agents confusing "how I work in this repo" with "how the product works".
