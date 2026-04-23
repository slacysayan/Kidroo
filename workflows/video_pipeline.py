"""Durable workflow: research → metadata → download → upload, per source video.

Shape:
    ┌──────────────┐
    │ orchestrate  │   (reads job row, resolves channel, computes schedule)
    └──────┬───────┘
           │  fan out (one Hatchet workflow run per video, concurrency ≤ 6/user)
           ▼
    ┌──────────────┐      ┌──────────────┐
    │ research     │ ───▶ │ metadata     │
    └──────────────┘      └──────┬───────┘
                                 ▼
                          ┌──────────────┐      ┌──────────────┐
                          │ download     │ ───▶ │ upload       │
                          └──────────────┘      └──────────────┘

Each step is a Hatchet `step` — retried independently with exponential
backoff. LLMUnavailableError is caught and re-raised as NonRetryableError so
Hatchet doesn't burn retries on an exhausted fallback chain.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from hatchet_sdk import Context
from hatchet_sdk.workflow import WorkflowMeta
from pydantic import BaseModel

from agents.download.agent import DownloadAgent, DownloadFileOutput, DownloadInput
from agents.lib.config import get_settings
from agents.lib.llm import LLMUnavailableError
from agents.lib.supabase import get_service_client
from agents.metadata.agent import MetadataAgent, MetadataInput
from agents.research.agent import ResearchAgent, ResearchInput
from agents.upload.agent import UploadAgent, UploadInput
from workflows.hatchet import hatchet

try:
    from hatchet_sdk import NonRetryableError  # type: ignore[attr-defined]
except Exception:  # pragma: no cover — older SDK versions
    class NonRetryableError(RuntimeError):  # type: ignore[no-redef]
        pass


class ProcessVideoInput(BaseModel):
    """Single-video workflow input."""

    job_id: str
    video_id: str                  # public.videos.id
    source_url: str
    source_video_id: str
    video_title: str
    video_description: str = ""
    duration_secs: int = 0
    channel_id: str                # public.channels.id
    channel_entity_id: str
    publish_at: datetime


@hatchet.workflow(
    name="process_video",
    on_events=["job:video_ready"],
    schedule_timeout="12h",
    timeout="2h",
)
class ProcessVideo(metaclass=WorkflowMeta):  # type: ignore[misc]
    """One source video → one upload. Runs many copies in parallel per job."""

    @hatchet.step(timeout="10m", retries=2)  # type: ignore[misc]
    async def research(self, ctx: Context) -> dict[str, Any]:
        inp = ProcessVideoInput.model_validate(ctx.workflow_input())
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
            raise NonRetryableError(str(e)) from e

    @hatchet.step(parents=["research"], timeout="5m", retries=2)  # type: ignore[misc]
    async def metadata(self, ctx: Context) -> dict[str, Any]:
        inp = ProcessVideoInput.model_validate(ctx.workflow_input())
        research_out = ctx.step_output("research")
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
            _persist_metadata(inp.video_id, out.model_dump(mode="json"))
            return out.model_dump(mode="json")
        except LLMUnavailableError as e:
            raise NonRetryableError(str(e)) from e

    @hatchet.step(parents=["metadata"], timeout="30m", retries=1)  # type: ignore[misc]
    async def download(self, ctx: Context) -> dict[str, Any]:
        inp = ProcessVideoInput.model_validate(ctx.workflow_input())
        async with DownloadAgent(job_id=inp.job_id, video_id=inp.video_id) as agent:
            out = await agent.run(DownloadInput(mode="download", url=inp.source_url))
        assert isinstance(out, DownloadFileOutput)
        return {"file_path": str(out.file_path), "bytes": out.bytes}

    @hatchet.step(parents=["download"], timeout="30m", retries=1)  # type: ignore[misc]
    async def upload(self, ctx: Context) -> dict[str, Any]:
        inp = ProcessVideoInput.model_validate(ctx.workflow_input())
        dl = ctx.step_output("download")
        md = ctx.step_output("metadata")
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
        _finalize_video(inp.video_id, out.yt_video_id, inp.publish_at)
        return out.model_dump(mode="json")


class ProcessVideoBatchInput(BaseModel):
    """Batch fanout — input shape that the API posts to Hatchet."""

    job_id: str
    channel_id: str
    channel_entity_id: str
    videos: list[dict[str, Any]]  # each validated as ProcessVideoInput sans publish_at
    schedule_per_day: int = 1
    schedule_start: datetime  # UTC midnight of start_date


@hatchet.workflow(name="process_video_batch", timeout="24h")
class ProcessVideoBatch(metaclass=WorkflowMeta):  # type: ignore[misc]
    """Orchestrates the full job: spread videos over the schedule and fan out."""

    @hatchet.step(timeout="5m")  # type: ignore[misc]
    async def plan(self, ctx: Context) -> dict[str, Any]:
        batch = ProcessVideoBatchInput.model_validate(ctx.workflow_input())
        return _spread_schedule(batch).model_dump(mode="json")

    @hatchet.step(parents=["plan"], timeout="24h")  # type: ignore[misc]
    async def fanout(self, ctx: Context) -> dict[str, Any]:
        plan = ctx.step_output("plan")
        settings = get_settings()
        semaphore = asyncio.Semaphore(settings.max_concurrent_videos_per_user)

        async def _spawn(inp: ProcessVideoInput) -> dict[str, Any]:
            async with semaphore:
                ref = await hatchet.admin.aio.run_workflow(
                    "process_video", inp.model_dump(mode="json")
                )
                return await ref.result()

        inputs = [ProcessVideoInput.model_validate(v) for v in plan["items"]]
        results = await asyncio.gather(
            *(_spawn(i) for i in inputs), return_exceptions=True
        )
        return {
            "total": len(inputs),
            "failed": sum(1 for r in results if isinstance(r, Exception)),
        }


process_video_batch = ProcessVideoBatch  # public alias


# ─── helpers ──────────────────────────────────────────────────────────────


class _ScheduledPlan(BaseModel):
    items: list[ProcessVideoInput]


def _spread_schedule(batch: ProcessVideoBatchInput) -> _ScheduledPlan:
    """Spread videos across days at the requested per-day cadence.

    Videos within a day are separated by `24h / per_day` so they don't all
    fire at midnight. All timestamps are UTC.
    """
    per_day = max(1, batch.schedule_per_day)
    slot = timedelta(hours=24 / per_day)
    items: list[ProcessVideoInput] = []
    for idx, raw in enumerate(batch.videos):
        day_offset = idx // per_day
        slot_idx = idx % per_day
        publish_at = (
            batch.schedule_start
            + timedelta(days=day_offset)
            + slot * slot_idx
        )
        publish_at = publish_at.astimezone(timezone.utc)
        items.append(
            ProcessVideoInput(
                job_id=batch.job_id,
                channel_id=batch.channel_id,
                channel_entity_id=batch.channel_entity_id,
                publish_at=publish_at,
                **raw,
            )
        )
    return _ScheduledPlan(items=items)


def _persist_metadata(video_id: str, meta: dict[str, Any]) -> None:
    supa = get_service_client()
    supa.table("videos").update(
        {
            "title": meta.get("title"),
            "description": meta.get("description"),
            "tags": meta.get("tags"),
            "hashtags": meta.get("hashtags"),
            "category_id": meta.get("category_id"),
            "status": "uploading",
        }
    ).eq("id", video_id).execute()


def _finalize_video(video_id: str, yt_video_id: str, publish_at: datetime) -> None:
    supa = get_service_client()
    supa.table("videos").update(
        {
            "yt_video_id": yt_video_id,
            "publish_at": publish_at.isoformat(),
            "status": "scheduled",
        }
    ).eq("id", video_id).execute()
