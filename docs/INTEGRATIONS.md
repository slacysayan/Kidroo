# Integrations — exact call signatures

Single source of truth for every external API the runtime touches. If a call in code disagrees with this file, either the code is wrong or this file is wrong — fix one in the same PR.

---

## Groq (primary LLM)

- **Endpoint:** OpenAI-compatible, `https://api.groq.com/openai/v1`
- **Env:** `GROQ_API_KEY`
- **Model slug:** `llama-3.1-70b-versatile`
- **Rate limit:** 14,400 requests/day (free tier)
- **SDK:** `groq` (Python)

```python
from groq import AsyncGroq

client = AsyncGroq(api_key=os.environ["GROQ_API_KEY"])

resp = await client.chat.completions.create(
    model="llama-3.1-70b-versatile",
    messages=[{"role": "system", "content": SYSTEM_PROMPT},
              {"role": "user", "content": user_input}],
    temperature=0.3,
    response_format={"type": "json_object"},   # for metadata agent
    max_tokens=1024,
)
```

---

## Cerebras (fallback LLM)

- **Endpoint:** `https://api.cerebras.ai/v1`
- **Env:** `CEREBRAS_API_KEY`
- **Model slug:** `llama3.1-70b`
- **Rate limit:** ~2,000 req/day free
- **SDK:** `cerebras-cloud-sdk` (Python)

```python
from cerebras.cloud.sdk import AsyncCerebras

client = AsyncCerebras(api_key=os.environ["CEREBRAS_API_KEY"])

resp = await client.chat.completions.create(
    model="llama3.1-70b",
    messages=[...],
    temperature=0.3,
)
```

### Failover wrapper

`agents/lib/llm.py` exposes `complete(messages, **kwargs)` which tries Groq first, catches `429 | 5xx`, logs `step='fallback'`, and retries on Cerebras. Agents never import Groq/Cerebras directly — they always go through `agents.lib.llm`.

---

## Firecrawl

- **Endpoint:** `https://api.firecrawl.dev/v1`
- **Env:** `FIRECRAWL_API_KEY`
- **SDK:** `firecrawl-py`
- **Rate limit:** 500 pages/month

```python
from firecrawl import FirecrawlApp

fc = FirecrawlApp(api_key=os.environ["FIRECRAWL_API_KEY"])

result = fc.scrape_url(
    url,
    params={
        "pageOptions": {"onlyMainContent": True},
        "formats": ["markdown"],
    },
)
# result["markdown"] — clean text for the research agent
```

Cache responses in Supabase table `firecrawl_cache` by `sha256(url)` with 7-day TTL.

---

## Exa

- **Endpoint:** `https://api.exa.ai`
- **Env:** `EXA_API_KEY`
- **SDK:** `exa_py`

```python
from exa_py import Exa

exa = Exa(os.environ["EXA_API_KEY"])

result = exa.search_and_contents(
    query=f"{video_title} {niche}",
    num_results=5,
    use_autoprompt=True,
    type="neural",
    text={"max_characters": 1000},
)
```

---

## yt-dlp

No auth. Python subprocess. Install via `uv tool install yt-dlp` (SKILLS.sh does this).

### Scan mode

```bash
yt-dlp --dump-json --flat-playlist --no-warnings <url>
```

Returns one JSON per line with fields: `id`, `title`, `duration`, `url`, `upload_date`, `uploader`, `view_count`.

### Download mode

```bash
yt-dlp \
  --output "/tmp/kidroo/{job_id}/{video_id}.%(ext)s" \
  --format "mp4/bestvideo+bestaudio" \
  --merge-output-format mp4 \
  --no-warnings \
  --newline \
  <video_url>
```

Progress parsing: each line of the form `[download]  67.3% of  ...` yields a progress update. Emit an `agent_logs` row at every full-percent boundary (or every 5 % for bandwidth-bound videos).

### Hardening

- Retry once on non-zero exit with `--no-check-certificate`.
- Set `--socket-timeout 30` to avoid wedging a worker.
- Enforce `MAX_DOWNLOAD_SIZE_MB=2000` via `--max-filesize`.

---

## Composio — YouTube

- **Toolkit slug:** `YOUTUBE` (version `20260413_01` as of writing)
- **Auth:** OAuth2, managed by Composio
- **SDK:** `composio` (Python)
- **Docs:** https://docs.composio.dev/toolkits/youtube.md

### Connecting a channel (one-time, per channel)

```bash
# CLI — interactive OAuth flow, produces a connection stored under <entity_id>
composio connections create --toolkit YOUTUBE --user-id finance_daily
```

Store the resulting `composio_entity_id` in the `channels` table.

### Actions used by the runtime

| Action slug | Purpose | Key params |
|---|---|---|
| `YOUTUBE_UPLOAD_VIDEO` | Upload a video file | `title`, `description`, `tags`, `categoryId`, `privacyStatus`, `videoFilePath` |
| `YOUTUBE_UPDATE_VIDEO` | Set `publishAt` post-upload | `id`, `status` |
| `YOUTUBE_GET_VIDEO` | Verify `uploadStatus` (ghost-upload check) | `id`, `part` |
| `YOUTUBE_LIST_CHANNEL_VIDEOS` | (optional) sanity-check the channel | `channelId` |

### Upload call

```python
from composio import Composio

composio = Composio(api_key=os.environ["COMPOSIO_API_KEY"])

# videoFilePath accepts either a local path (Composio uploads to R2 for you)
# or a pre-uploaded s3key. Prefer local path for simplicity.
resp = composio.actions.execute(
    action="YOUTUBE_UPLOAD_VIDEO",
    entity_id=channel_entity_id,
    params={
        "title": meta["title"],
        "description": meta["description"],
        "tags": meta["tags"],
        "categoryId": str(meta["category_id"]),
        "privacyStatus": "private",
        "videoFilePath": file_path,   # local path
    },
)
assert resp["successful"] is True, resp["error"]
yt_video_id = resp["data"]["id"]
```

### Post-upload verification (mitigates [composio#2954](https://github.com/ComposioHQ/composio/issues/2954))

Poll `YOUTUBE_GET_VIDEO` until `status.uploadStatus == "uploaded"` AND `fileDetails.fileSize` is non-null. Cap at 6 polls × 10 s = 60 s. If the check never passes, delete the ghost video and retry the upload (max 3 total attempts).

### Scheduling via `publishAt`

YouTube Data API supports `status.publishAt` (ISO 8601 UTC) when `privacyStatus='private'`. At video-reveal time YouTube auto-flips privacy to public.

**Known unknown:** whether `YOUTUBE_UPLOAD_VIDEO` accepts `publishAt` directly in its initial params varies by Composio toolkit version. **Phase 2 entry criterion** is to probe this on the pinned version. Current plan:

1. Upload with `privacyStatus='private'` only.
2. Call `YOUTUBE_UPDATE_VIDEO` with `{"status": {"privacyStatus": "private", "publishAt": "<ISO>"}}`.

This two-call pattern is guaranteed to work across versions.

### Quota note

YouTube Data API quota is **per Google Cloud project**, not per channel. The default managed-Composio OAuth app has strict shared quota. For production Composio recommends [creating a custom OAuth app](https://composio.dev/auth/googleapps) per project. Plan one GCP project per YouTube channel if you need >6 uploads/day in aggregate.

---

## Supabase

- **SDKs:** `supabase` (Python, for server) + `@supabase/supabase-js` (Next.js)
- **Env:** `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`

### Python (server)

```python
from supabase import create_client

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_KEY"],        # service role — server only
)
supabase.table("agent_logs").insert({
    "job_id": job_id,
    "video_id": video_id,
    "agent": "research",
    "step": "tool_call",
    "message": "firecrawl.scrape_url",
    "metadata": {"latency_ms": 842, "cache_hit": False},
}).execute()
```

### TypeScript (browser)

```ts
import { createClient } from "@supabase/supabase-js"

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,    // anon — RLS enforced
)

const channel = supabase
  .channel(`job-${jobId}`)
  .on("postgres_changes",
      { event: "INSERT", schema: "public", table: "agent_logs", filter: `job_id=eq.${jobId}` },
      (payload) => onLog(payload.new))
  .subscribe()
```

---

## Hatchet

- **Env:** `HATCHET_CLIENT_TOKEN`, `HATCHET_CLIENT_HOST_PORT`
- **SDK:** `hatchet-sdk` (Python)
- **Docs:** https://docs.hatchet.run

### Worker

```python
from hatchet_sdk import Hatchet, Context

hatchet = Hatchet()

process_video = hatchet.workflow(name="process-single-video")

@process_video.task(execution_timeout="30m", retries=3)
async def run(input: ProcessVideoInput, ctx: Context) -> dict:
    ...
```

### Dispatching

```python
run = await hatchet.admin.run_workflow(
    "process-video-batch",
    input={"job_id": job_id, "video_ids": [...], "channel_entity_id": ..., "schedule": {...}},
    options={"additional_metadata": {"user_id": user_id}},
)
```

### Concurrency group

```python
@process_video.task(
    execution_timeout="30m",
    concurrency=ConcurrencyExpression(
        expression="input.user_id",
        max_runs=6,
        limit_strategy="GROUP_ROUND_ROBIN",
    ),
)
```
