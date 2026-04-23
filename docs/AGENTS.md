# Runtime agent specifications

Five agents. Each lives under `agents/<name>/` and exposes the base contract declared in [`../AGENTS.md`](../AGENTS.md#runtime-agent-contract-the-five-agents).

---

## Shared contract

Every agent implements:

```python
from agents.lib.base import BaseAgent, AgentInput, AgentOutput

class <Name>Agent(BaseAgent):
    name: str  # matches folder name

    async def run(self, input: AgentInput) -> AgentOutput: ...
```

Every agent writes structured rows to `agent_logs`:

| `step` | When | `message` example |
|---|---|---|
| `status` | Started / finished | `"started"` / `"completed"` |
| `tool_call` | Before each tool invocation | `"firecrawl.scrape_url(url=...)"` |
| `reasoning` | LLM output that informs the plan | `"Identified niche: consumer tech"` |
| `fallback` | LLM provider failover | `"Groq 429 → Cerebras"` |
| `error` | Any exception | `"yt-dlp exited 1: HTTP 403"` |

`metadata` is a free-form JSONB column used for `{tool, latency_ms, response_bytes, retry_attempt, trace_id}`.

---

## Agent 1 — Orchestrator

| Field | Value |
|---|---|
| Folder | `agents/orchestrator/` |
| Model | Groq LLaMA 3.1 70B Versatile (fallback Cerebras) |
| Tools | none (reasoning only) |
| Input | `{user_message: str, job_context: dict, available_channels: list[Channel]}` |
| Output | `{channel_entity_id: str, schedule: {per_day: int, start_date: str}, video_ids: list[str]}` |

### System prompt

```
You are the orchestrator for a YouTube content automation pipeline.

Your job:
1. Parse the user's intent from their message.
2. Identify the target YouTube channel by matching to `available_channels`.
3. Determine the schedule (videos per day, ISO start date).
4. Confirm the list of selected video IDs from the job context.
5. Output a structured JSON task plan — nothing else.

Output ONLY valid JSON matching this schema:
  {"channel_entity_id": str, "schedule": {"per_day": int, "start_date": "YYYY-MM-DD"}, "video_ids": [str, ...]}

No preamble. No markdown. No explanation.
```

---

## Agent 2 — Research

| Field | Value |
|---|---|
| Folder | `agents/research/` |
| Model | Groq LLaMA 3.1 70B Versatile |
| Tools | Firecrawl (`scrape_url`), Exa (`search`) |
| Input | `{source_url: str, video_title: str, video_description: str}` |
| Output | `{niche: str, keywords: list[str], trending_angles: list[str], raw_context: str}` |

### Tool call patterns

```python
# Firecrawl
firecrawl.scrape_url(
    source_url,
    params={"pageOptions": {"onlyMainContent": True}},
)

# Exa — semantic query informed by the scrape
exa.search(
    query=f"{video_title} {niche_keyword}",
    num_results=5,
    use_autoprompt=True,
)
```

### Caching

Scrape responses are cached in Supabase `firecrawl_cache` keyed by `sha256(url)` with 7-day TTL. Cache hits skip the network call but still emit a `tool_call` log with `metadata.cache_hit = true`.

---

## Agent 3 — Metadata

| Field | Value |
|---|---|
| Folder | `agents/metadata/` |
| Model | Groq LLaMA 3.1 70B Versatile |
| Tools | none |
| Input | Research output + `{video_title, duration_secs}` |
| Output | `{title: str, description: str, tags: list[str], hashtags: list[str], category_id: int, publish_at: str}` |

### System prompt

```
You are a YouTube SEO expert. Generate metadata for a single video.

Rules:
- Title: under 60 characters, keyword-first, no clickbait.
- Description: 200–250 words. Include 3 timestamps (00:00, a keyword moment, conclusion).
  End with a clear call to action.
- Tags: exactly 15 — mix broad and specific, all lowercase.
- Hashtags: exactly 3, relevant to niche.
- category_id: integer from the YouTube category taxonomy.
- publish_at: ISO-8601 datetime, UTC — exactly as provided in the input.

Output ONLY valid JSON. No markdown. No explanation.
```

---

## Agent 4 — Download

| Field | Value |
|---|---|
| Folder | `agents/download/` |
| Model | none (subprocess only) |
| Tools | `ytdlp` skill (`agents/download/skills/ytdlp.py`) |
| Input | `{mode: "scan" \| "download", url: str, job_id?: str, video_id?: str}` |
| Output | scan → `list[VideoMeta]`; download → `{file_path: str, bytes: int}` |

### Implementation

```python
# Scan — instant, metadata only
result = await asyncio.create_subprocess_exec(
    "yt-dlp", "--dump-json", "--flat-playlist", "--no-warnings", url,
    stdout=asyncio.subprocess.PIPE,
)
stdout, _ = await result.communicate()
videos = [json.loads(line) for line in stdout.decode().strip().split("\n")]

# Download — streamed to /tmp/kidroo/{job_id}/{video_id}.mp4
proc = await asyncio.create_subprocess_exec(
    "yt-dlp",
    "--output", f"/tmp/kidroo/{job_id}/{video_id}.%(ext)s",
    "--format", "mp4/bestvideo+bestaudio",
    "--merge-output-format", "mp4",
    "--no-warnings",
    "--newline",                       # one progress line per line of stdout
    url,
    stdout=asyncio.subprocess.PIPE,
)
# Parse progress lines and insert agent_logs rows every ~5% change.
```

---

## Agent 5 — Upload

| Field | Value |
|---|---|
| Folder | `agents/upload/` |
| Model | none (Composio SDK) |
| Tools | Composio `YOUTUBE_UPLOAD_VIDEO`, optionally `YOUTUBE_UPDATE_VIDEO` |
| Input | `{file_path: str, metadata: Metadata, channel_entity_id: str}` |
| Output | `{yt_video_id: str, publish_at: str, privacy_status: str}` |

### Implementation sketch

```python
from composio import Composio

composio = Composio(api_key=os.environ["COMPOSIO_API_KEY"])

# Step 1: upload via Composio (metadata + file bytes)
resp = composio.actions.execute(
    action="YOUTUBE_UPLOAD_VIDEO",
    entity_id=channel_entity_id,   # routes to correct channel
    params={
        "title": metadata["title"],
        "description": metadata["description"],
        "tags": metadata["tags"],
        "categoryId": str(metadata["category_id"]),
        "privacyStatus": "private",
        "videoFilePath": file_path,   # local path
    },
)
yt_video_id = resp["data"]["id"]

# Step 2: verify the bytes actually transferred (mitigates composio bug #2954)
for _ in range(6):
    await asyncio.sleep(10)
    v = composio.actions.execute(
        action="YOUTUBE_GET_VIDEO",
        entity_id=channel_entity_id,
        params={"id": yt_video_id, "part": "status,fileDetails"},
    )
    if v["data"]["items"][0]["status"]["uploadStatus"] == "uploaded":
        break
else:
    raise UploadVerificationError(f"ghost upload: {yt_video_id}")

# Step 3: schedule via publishAt
composio.actions.execute(
    action="YOUTUBE_UPDATE_VIDEO",
    entity_id=channel_entity_id,
    params={
        "id": yt_video_id,
        "status": {"privacyStatus": "private", "publishAt": metadata["publish_at"]},
    },
)
```

> **Open item:** Phase 2 must confirm whether `YOUTUBE_UPLOAD_VIDEO` accepts `publishAt` directly in its params or whether a follow-up `YOUTUBE_UPDATE_VIDEO` is always required. See [`INTEGRATIONS.md`](INTEGRATIONS.md).

---

## Adding a new runtime agent

1. Create `agents/<new_name>/` with `__init__.py`, `agent.py`, and `skills/` (if the agent calls external tools).
2. Subclass `BaseAgent` and implement `run()`.
3. Add the agent to `agents/__init__.py` so `from agents import <Name>Agent` works.
4. Add a section to this file (`docs/AGENTS.md`) documenting input/output/tools/prompt.
5. Add a unit test in `tests/unit/agents/test_<new_name>.py`.
6. Update `.agents/skills/agents-runtime/SKILL.md` if conventions change.
