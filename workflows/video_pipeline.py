"""Durable workflow: per-video DAG — download runs in parallel with research.

Shape:
    ┌──────────────┐
    │  plan / fan  │   (reads job row, resolves channel, computes schedule)
    └──────┬───────┘
           │  fan out (one `process_video` run per video, concurrency ≤ 6/user)
           ▼
    ┌──────────────┐                           ┌──────────────┐
    │ research     │ ──▶ ┌──────────────┐ ──┐  │ download     │
    └──────────────┘     │ metadata     │   │  └──────┬───────┘
                         └──────────────┘   ├──▶ ┌──────────────┐
                                            │    │ upload       │
                                            └──▶ └──────────────┘

`research` and `download` have no parents so they execute concurrently.
`metadata` depends on `research`. `upload` depends on both `download` and
`metadata`.

Uses the Hatchet v1 SDK: `hatchet.workflow(...).task(...)` with `parents=[...]`
for DAG edges. LLMUnavailableError is re-raised as NonRetryableException so
Hatchet stops burning retries on an exhausted fallback chain.
"""
from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path
from typing import Any

from hatchet_sdk import Context, NonRetryableException

from agents.download.agent import DownloadAgent, DownloadFileOutput, DownloadInput
from agents.lib.config import get_settings
from agents.lib.llm import LLMUnavailableError
from agents.lib.supabase import get_service_client
from agents.metadata.agent import MetadataAgent, MetadataInput
from agents.research.agent import ResearchAgent, ResearchInput
from agents.upload.agent import UploadAgent, UploadInput
from workflows.hatchet import hatchet
from workflows.pipeline_models import (
    ProcessVideoBatchInput,
    ProcessVideoInput,
    _finalize_video_payload,
    _persist_metadata_payload,
    _spread_schedule,
)

# ─── process_video: one video end-to-end ──────────────────────────────────

process_video = hatchet.workflow(
    name="process_video",
    input_validator=ProcessVideoInput,
)


@process_video.task(
    name="research",
    execution_timeout=timedelta(minutes=10),
    retries=2,
)
async def research_task(inp: ProcessVideoInput, ctx: Context) -> dict[str, Any]:
    try:
        async with ResearchAgent(job_id=inp.job_id, video_id=inp.video_id) as agent:
            out = await agent.run(
                ResearchInput(
                    source_url=inp.source_url,
                    video_title=inp.video_title,
                    video_description=inp.video_description,
                )
            )
        return out.model_dump(mode="json")
    except LLMUnavailableError as e:
        raise NonRetryableException(str(e)) from e


@process_video.task(
    name="metadata",
    parents=[research_task],
    execution_timeout=timedelta(minutes=5),
    retries=2,
)
async def metadata_task(inp: ProcessVideoInput, ctx: Context) -> dict[str, Any]:
    research_out = ctx.task_output(research_task)
    try:
        async with MetadataAgent(job_id=inp.job_id, video_id=inp.video_id) as agent:
            out = await agent.run(
                MetadataInput(
                    research=research_out,  # type: ignore[arg-type]
                    video_title=inp.video_title,
                    duration_secs=inp.duration_secs,
                    publish_at=inp.publish_at,
                )
            )
        payload = out.model_dump(mode="json")
        await asyncio.to_thread(
            lambda: get_service_client()
            .table("videos")
            .update(_persist_metadata_payload(payload))
            .eq("id", inp.video_id)
            .execute()
        )
        return payload
    except LLMUnavailableError as e:
        raise NonRetryableException(str(e)) from e


@process_video.task(
    name="download",
    execution_timeout=timedelta(minutes=30),
    retries=1,
)
async def download_task(inp: ProcessVideoInput, ctx: Context) -> dict[str, Any]:
    async with DownloadAgent(job_id=inp.job_id, video_id=inp.video_id) as agent:
        out = await agent.run(DownloadInput(mode="download", url=inp.source_url))
    assert isinstance(out, DownloadFileOutput)
    return {"file_path": str(out.file_path), "bytes": out.bytes}


@process_video.task(
    name="upload",
    parents=[download_task, metadata_task],
    execution_timeout=timedelta(minutes=30),
    retries=1,
)
async def upload_task(inp: ProcessVideoInput, ctx: Context) -> dict[str, Any]:
    dl = ctx.task_output(download_task)
    md = ctx.task_output(metadata_task)
    async with UploadAgent(job_id=inp.job_id, video_id=inp.video_id) as agent:
        out = await agent.run(
            UploadInput(
                channel_id=inp.channel_id,
                channel_entity_id=inp.channel_entity_id,
                source_video_id=inp.source_video_id,
                file_path=Path(str(dl["file_path"])),
                title=str(md["title"]),
                description=str(md["description"]),
                tags=list(md.get("tags", [])),
                category_id=int(md["category_id"]),
                publish_at=inp.publish_at,
            )
        )
    await asyncio.to_thread(
        lambda: get_service_client()
        .table("videos")
        .update(_finalize_video_payload(out.yt_video_id, inp.publish_at))
        .eq("id", inp.video_id)
        .execute()
    )
    return out.model_dump(mode="json")


# ─── process_video_batch: fan-out across the selected videos ──────────────

process_video_batch = hatchet.workflow(
    name="process_video_batch",
    input_validator=ProcessVideoBatchInput,
)


@process_video_batch.task(
    name="plan",
    execution_timeout=timedelta(minutes=1),
)
async def plan_task(inp: ProcessVideoBatchInput, ctx: Context) -> dict[str, Any]:
    return _spread_schedule(inp).model_dump(mode="json")


@process_video_batch.task(
    name="fanout",
    parents=[plan_task],
    execution_timeout=timedelta(hours=24),
)
async def fanout_task(inp: ProcessVideoBatchInput, ctx: Context) -> dict[str, Any]:
    plan = ctx.task_output(plan_task)
    settings = get_settings()
    sem = asyncio.Semaphore(settings.max_concurrent_videos_per_user)

    async def _spawn(video_input: ProcessVideoInput) -> Any:
        async with sem:
            return await process_video.aio_run(video_input)

    inputs = [ProcessVideoInput.model_validate(v) for v in plan["items"]]
    results = await asyncio.gather(
        *(_spawn(v) for v in inputs), return_exceptions=True
    )
    failed = sum(1 for r in results if isinstance(r, Exception))
    return {"total": len(inputs), "failed": failed}
