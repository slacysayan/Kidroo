# Skill — Hatchet (durable workflows)

Read this when you are writing or modifying a Hatchet workflow.

## Prerequisites

- `HATCHET_CLIENT_TOKEN` + `HATCHET_CLIENT_HOST_PORT` in `.env`.
- `hatchet-sdk` in `pyproject.toml`.
- Read `docs/INTEGRATIONS.md#hatchet` for call signatures.

## Why Hatchet

Trigger.dev's UX (agent todos, multi-step visibility, resumable checkpoints) is exactly what we want, but Trigger.dev is TypeScript-only. Hatchet is the Python-native equivalent: Postgres-backed, checkpointed, concurrency-aware, and fully free to self-host.

## Workflow anatomy

```python
# workflows/video_pipeline.py
from hatchet_sdk import Hatchet, Context
from pydantic import BaseModel

hatchet = Hatchet()

class ProcessSingleVideoInput(BaseModel):
    job_id: str
    video_id: str
    channel_entity_id: str
    schedule_slot: str       # ISO 8601

process_single_video = hatchet.workflow(name="process-single-video")

@process_single_video.task(execution_timeout="30m", retries=3)
async def run(input: ProcessSingleVideoInput, ctx: Context) -> dict:
    # concurrent: download + research
    file_path, context = await asyncio.gather(
        _download(input, ctx),
        _research(input, ctx),
    )
    metadata = await _generate_metadata(context, input, ctx)
    yt_video_id = await _upload(file_path, metadata, input.channel_entity_id, ctx)
    return {"yt_video_id": yt_video_id}
```

## Concurrency groups

Cap concurrent runs per user at 6:

```python
from hatchet_sdk import ConcurrencyExpression

@process_single_video.task(
    execution_timeout="30m",
    concurrency=ConcurrencyExpression(
        expression="input.user_id",
        max_runs=6,
        limit_strategy="GROUP_ROUND_ROBIN",
    ),
)
```

## Fan-out from a parent workflow

```python
@process_batch.task()
async def run(input: BatchInput, ctx: Context) -> dict:
    children = [
        process_single_video.aio_run(
            ProcessSingleVideoInput(...),
            options={"additional_metadata": {"parent_job_id": input.job_id}},
        )
        for video_id in input.video_ids
    ]
    results = await asyncio.gather(*children)
    return {"completed": len(results)}
```

## Checkpointing

Hatchet checkpoints between tasks automatically. If the worker process dies mid-run, the control plane re-dispatches from the last completed task. For mid-task durability (e.g. a long yt-dlp download), split the step into multiple small tasks so progress survives restarts.

## Testing resumability

```bash
# Terminal 1: start the worker
uv run python -m workflows.worker

# Terminal 2: submit a 3-video job via the test script
uv run python scripts/test_kill_resume.py

# Terminal 1: kill the worker mid-run
# Ctrl+C

# Restart it
uv run python -m workflows.worker

# The job should resume from the last completed step and all 3 videos should land scheduled.
```

This test is automated in `tests/integration/test_resumability.py` (Phase 3).

## Retries

Per-task retry policy:

```python
@process_single_video.task(
    retries=3,
    backoff_factor=2,         # 30s, 60s, 120s
    backoff_max_seconds=300,
)
```

Only retry on transient errors. Authentication / permission errors should raise `NonRetryableError` so Hatchet stops immediately.

## Logging

Every task should emit `agent_logs` rows for visibility. Use the `agents.lib.logging.JobLogger` context manager:

```python
async with JobLogger(job_id=input.job_id, video_id=input.video_id, agent="orchestrator") as log:
    await log("status", "started")
    ...
    await log("status", "completed")
```

## Common failures

| Symptom | Fix |
|---|---|
| Worker connects but no tasks arrive | Check `HATCHET_CLIENT_HOST_PORT`; worker and dispatcher must be on the same Hatchet instance |
| Task retries infinitely on an auth error | Raise `hatchet_sdk.NonRetryableError` to stop retries |
| Fan-out runs serially instead of in parallel | You used `await x.run()` in a loop instead of `asyncio.gather(*[x.aio_run(...)])` |
| Concurrency group doesn't take effect | Expression must be a valid JSONPath-style string into `input` |

## Related files

- `docs/INTEGRATIONS.md` — Hatchet call signatures
- `workflows/video_pipeline.py` (Phase 3)
- `agents/lib/logging.py` — `JobLogger`
