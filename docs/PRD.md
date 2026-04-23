# Product requirements document — Kidroo

**Version:** 1.1 (reconciled)
**Status:** Ready for development
**Users:** 4–5 internal collaborators
**Infra budget:** Free tiers only
**Inspiration:** [kairos.computer](https://kairos.computer)

> **Changelog vs v1.0:**
> - Replaced Trigger.dev (TypeScript-only) with **Hatchet** (Python-native, Postgres-backed durable workflows). Temporal is the documented fallback.
> - Replaced Railway (no true free tier) with **Koyeb free**.
> - Removed **LangChain** — CrewAI already abstracts LLM config; the extra layer was redundant.
> - Removed redundant WebSocket layer — all realtime streaming now goes through **Supabase Realtime** only. FastAPI exposes plain REST.
> - Added **GSAP** as the primary animation library (alongside Framer Motion for shadcn-native entrances).
> - Corrected the YouTube quota model (quota is per **Google Cloud project**, not per channel).
> - Added a **ToS & Content ID risk register** (§15).

---

## 1. Problem statement

Running multiple faceless YouTube channels manually is unsustainable at any meaningful scale. Current friction:

- Source discovery requires navigating multiple platforms by hand.
- Each download is a separate manual step.
- Writing SEO titles, descriptions, and tags per video is slow and repetitive.
- Uploading to the correct owned channel requires logging into each one separately.
- Managing 10+ channels means repeating every step 10+ times.

There is no existing tool that takes a YouTube channel or video link, retrieves the videos, generates metadata for each, and schedules uploads to one or more owned channels — from a single chat prompt.

---

## 2. Solution

A chat-first, agent-native web application. The user pastes a YouTube URL into the chat; a coordinated system of five AI agents scans the channel, generates SEO metadata, downloads the videos in the background, and uploads to owned YouTube channels via Composio's OAuth bridge. All without leaving the chat interface.

Three design principles:

1. **Agent activity is the hero.** The UI does not hide what is happening. Every agent step — tool calls, LLM reasoning, progress — streams live.
2. **Resumability is non-negotiable.** Hatchet checkpoints every step. Closing the tab does not lose the job. Jobs survive server restarts.
3. **Zero cost at this scale.** Every service has a free tier sufficient for 4–5 users with 10–15 channels.

---

## 3. Users and scope

**Primary users:** 4–5 internal collaborators managing faceless YouTube channels.

**Auth model:** single internal app with magic-link login. Each app user can connect **multiple** YouTube channels via Composio OAuth. Channels are stored as named Composio entity IDs (e.g. `finance_daily`, `tech_weekly`) in the `channels` table, scoped per user.

**Scale ceiling (free tiers):**
- Groq: 14,400 LLM req/day → ~3,600 videos/day at ~4 LLM calls each.
- Cerebras: ~2,000 LLM req/day as failover.
- Firecrawl: 500 pages/month → use a 7-day URL-keyed cache.
- Exa: free tier.
- Supabase: 500 MB DB, 2 GB realtime bandwidth, free auth.
- Hatchet: free self-host on Koyeb OR free cloud tier.
- YouTube: **6 uploads per day per Google Cloud project** (upload costs ~1,600 units of a 10k-unit default quota). For per-channel quota, provision one GCP project + Composio custom OAuth app per channel. Phase 2 exits with quota strategy chosen.

---

## 4. Core user flow

```
User opens app → authenticated via Supabase magic link
     │
     ▼
Chat interface loads, sidebar shows connected channels (Composio entities)
     │
     ▼
User pastes: https://youtube.com/@sourcechannel
             (or a single video URL, or a playlist URL)
     │
     ▼
System:  "Scanning channel..."
  [Research agent + yt-dlp metadata scan — NO download yet]
     │
     ▼
Inline video-selection card appears in chat:
  - Full video list with title + duration
  - Checkboxes (individual + select all)
  - Target channel dropdown (mapped to Composio entity IDs)
  - Schedule picker: "2/day starting Monday", "1/day", "upload now"
     │
     ▼
User selects videos → "Upload these to Finance Daily, 2 per day"
     │
     ▼
Orchestrator reads intent → fans out to parallel per-video workflows
  (one Hatchet workflow run per video, capped at 6 concurrent per user)
     │
     ▼
Per video, concurrently:
  - Download agent: yt-dlp to /tmp (background, progress % streamed)
  - Research agent: Firecrawl + Exa enrichment
  - Metadata agent: Groq generates title + description + tags + hashtags
  - Upload agent: fires when both download + metadata complete
     │
     ▼
Every step streams to chat in real time via Supabase Realtime:
  [Research]  Scraped source page — niche: consumer tech
  [Metadata]  Generated title: "Why the iPhone 16 changes everything"
  [Download]  yt-dlp: 67%
  [Upload]    Composio → uploading to Finance Daily
  [Upload]    Scheduled: Monday 9:00am ✓
     │
     ▼
Schedule-confirmation card appears
Job persists in Supabase — user can close tab and return
```

---

## 5. Technical stack

### Frontend

| Component | Tool | Justification |
|---|---|---|
| Framework | Next.js 15 (App Router) | React 19, Vercel-native, free deploy |
| Hosting | Vercel | Free tier, instant deploys |
| UI kit | shadcn/ui | Owned code, composable |
| Styling | Tailwind CSS v4 | shadcn dependency |
| Animation (primary) | **GSAP** | Agent-log timeline, scroll-triggered transitions |
| Animation (shadcn) | **Framer Motion** | Entrances/exits for shadcn primitives |
| Typography | Geist Sans + Geist Mono | Vercel free font |
| Realtime | Supabase JS client | Single realtime channel: `agent_logs` |

### Backend

| Component | Tool | Justification |
|---|---|---|
| Server | FastAPI (Python 3.11) | Async, typed, CrewAI-native |
| Hosting | **Koyeb free** | True always-on free VM (Railway free tier expired) |
| Dep mgr | **uv** | Fast, deterministic |

### Workflow

| Component | Tool | Justification |
|---|---|---|
| Durable orchestrator | **Hatchet** | Python SDK, Postgres-backed, checkpointed |
| Fallback | Temporal (Python) | If Hatchet proves insufficient |
| Concurrency | `max_concurrency=6` per user | Hatchet concurrency group on `user_id` |

### Database & auth

| Component | Tool |
|---|---|
| Database | Supabase Postgres |
| Realtime | Supabase Realtime (`agent_logs` table) |
| Auth | Supabase Auth — magic link + email allowlist |
| Storage | Supabase Storage (thumbnails, temp refs) |

### AI & agents

| Component | Tool |
|---|---|
| Agent framework | CrewAI |
| LLM primary | Groq — LLaMA 3.1 70B Versatile |
| LLM fallback | Cerebras — LLaMA 3.1 70B |
| LLM config | **CrewAI native** (no LangChain) |

### External tools

| Tool | Role | Auth |
|---|---|---|
| Firecrawl | Scrape source page → markdown | API key |
| Exa | Semantic niche/trend search | API key |
| yt-dlp | Scan + download | No key |
| Composio | YouTube OAuth + upload | API key + per-channel OAuth |

---

## 6. System architecture

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full canvas + data flow diagram.

---

## 7. Database schema

Canonical migration lives at `supabase/migrations/001_initial_schema.sql`. Four tables:

- `jobs` — one row per user submission (`source_url`, `status`, `channel_id`, `schedule`)
- `videos` — one row per video in a job (`title`, `description`, `tags`, `status`, `yt_video_id`, `publish_at`)
- `agent_logs` — append-only log stream (`job_id`, `video_id`, `agent`, `step`, `message`, `metadata`, `trace_id`)
- `channels` — connected YouTube channels per user (`name`, `composio_entity_id`, `yt_channel_id`, `connected`)

Realtime is enabled on `agent_logs` only.

---

## 8. Agents

See [`AGENTS.md`](AGENTS.md) (in `docs/`) for the full per-agent specification. Summary:

| # | Agent | Model | Tools | Output |
|---|---|---|---|---|
| 1 | Orchestrator | Groq 70B | (none — reasoning only) | JSON task plan |
| 2 | Research | Groq 70B | Firecrawl, Exa | Context blob |
| 3 | Metadata | Groq 70B | (none) | `{title, description, tags[], hashtags[], category_id, publish_at}` |
| 4 | Download | (no LLM) | yt-dlp subprocess | Local file path or scan list |
| 5 | Upload | (no LLM) | Composio `YOUTUBE_UPLOAD_VIDEO` | YouTube video ID + scheduled `publishAt` |

---

## 9. API keys

Full list lives in [`.env.example`](../.env.example) and [`README.md#api-keys-required`](../README.md#api-keys-required).

---

## 10. Durable workflow — Hatchet

```python
# workflows/video_pipeline.py (sketch — full code in Phase 2)

from hatchet_sdk import Hatchet, Context
from pydantic import BaseModel

hatchet = Hatchet()

class BatchInput(BaseModel):
    job_id: str
    video_ids: list[str]
    channel_entity_id: str
    schedule: dict

process_batch = hatchet.workflow(name="process-video-batch")
process_video = hatchet.workflow(name="process-single-video")

@process_batch.task()
async def run(input: BatchInput, ctx: Context) -> dict:
    # fan out one child workflow per video, bounded by concurrency group
    results = await ctx.aio.spawn_workflows(
        [(process_video, {"job_id": input.job_id, "video_id": v, ...}) for v in input.video_ids]
    )
    return {"completed": len(results)}

@process_video.task(execution_timeout="30m")
async def run(input: dict, ctx: Context) -> dict:
    # concurrent: download + research
    download, context = await asyncio.gather(
        download_video(input),
        research_video(input),
    )
    metadata = await generate_metadata(context, input)
    yt_video_id = await upload_video(download, metadata, input["channel_entity_id"])
    return {"yt_video_id": yt_video_id}
```

Resumability: if the Hatchet worker process dies mid-run, the control plane re-dispatches from the last completed step. Phase 3 exits with a verified kill-mid-run test.

---

## 11. Frontend realtime

```ts
// apps/web/hooks/useAgentLogs.ts
import { useEffect, useState } from "react"
import { createClient } from "@/lib/supabase/client"

export function useAgentLogs(jobId: string) {
  const [logs, setLogs] = useState<AgentLog[]>([])
  const supabase = createClient()

  useEffect(() => {
    supabase
      .from("agent_logs")
      .select("*")
      .eq("job_id", jobId)
      .order("created_at", { ascending: true })
      .then(({ data }) => setLogs(data ?? []))

    const channel = supabase
      .channel(`job-${jobId}`)
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "agent_logs", filter: `job_id=eq.${jobId}` },
        (payload) => setLogs((prev) => [...prev, payload.new as AgentLog])
      )
      .subscribe()

    return () => { supabase.removeChannel(channel) }
  }, [jobId])

  return logs
}
```

---

## 12. Repository structure

See [`README.md#repository-layout`](../README.md#repository-layout).

---

## 13. UI spec

See [`UI_SPEC.md`](UI_SPEC.md).

---

## 14. Error handling

| Failure | Detection | Response |
|---|---|---|
| yt-dlp fetch fails | Non-zero exit code | Retry once with `--no-check-certificate`; else mark video `failed` |
| Groq 429 | HTTP 429 | Route to Cerebras; log `step: "fallback"` |
| Cerebras 429 | HTTP 429 | Hatchet retry with 60 s backoff |
| Composio upload error | Non-zero response | Hatchet retry 3× (30 s, 60 s, 120 s); then notify in chat |
| Composio ghost-upload (bug #2954) | `fileDetails.fileSize == null` on YouTube after 60 s | Hatchet compensating action: delete ghost + re-upload; cap at 3 retries |
| Supabase disconnect | Realtime close | JS client auto-reconnects |
| Koyeb restart | Process exit | Hatchet resumes from last checkpoint |
| YouTube quota exceeded | Composio error code | Queue remaining to next day; show remaining schedule in chat |
| `/tmp` full | OSError | Reject new downloads; purge failed-job temp files |

---

## 15. Risks register

See [`README.md#risks--open-items`](../README.md#risks--open-items). Top items:

1. **YouTube ToS & Content ID** — uploading third-party content is a policy risk.
2. **Composio upload ghost-video bug** (#2954) — needs post-upload verification.
3. **`publishAt` support in Composio** — needs Phase 2 verification; fallback via `YOUTUBE_UPDATE_VIDEO`.
4. **Quota model** — one GCP project = ~6 uploads/day aggregate.
5. **Firecrawl 500/mo** — cache required.
6. **Ephemeral `/tmp`** — stream or bound concurrency.
7. **Magic-link allowlist** — must be enforced at RLS + `before_signup` Edge Function.

---

## 16. Delivery phases

See [`ROADMAP.md`](ROADMAP.md).
