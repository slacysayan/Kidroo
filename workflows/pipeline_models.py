"""Pure-Python models + helpers for the video pipeline.

Kept separate from `workflows.video_pipeline` so unit tests can import the
scheduling math without pulling in the Hatchet SDK.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel


class ProcessVideoInput(BaseModel):
    """Single-video workflow input."""

    job_id: str
    video_id: str
    source_url: str
    source_video_id: str
    video_title: str
    video_description: str = ""
    duration_secs: int = 0
    channel_id: str
    channel_entity_id: str
    publish_at: datetime


class ProcessVideoBatchInput(BaseModel):
    """Batch fanout input — the API posts this shape to Hatchet."""

    job_id: str
    channel_id: str
    channel_entity_id: str
    videos: list[dict[str, Any]]
    schedule_per_day: int = 1
    schedule_start: datetime  # UTC midnight of start_date


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
            batch.schedule_start + timedelta(days=day_offset) + slot * slot_idx
        ).astimezone(UTC)
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


def _persist_metadata_payload(meta: dict[str, Any]) -> dict[str, Any]:
    """Map a metadata agent output to the `videos` update payload."""
    return {
        "title": meta.get("title"),
        "description": meta.get("description"),
        "tags": meta.get("tags"),
        "hashtags": meta.get("hashtags"),
        "category_id": meta.get("category_id"),
        "status": "uploading",
    }


def _finalize_video_payload(
    yt_video_id: str,
    publish_at: datetime,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Map a successful upload to the `videos` update payload.

    The idempotency_key must be persisted here — `UploadAgent` looks it up on
    retry to short-circuit duplicate uploads, and a missing column leaves the
    guard dead (every retry re-uploads to YouTube and burns the daily quota).
    """
    payload: dict[str, Any] = {
        "yt_video_id": yt_video_id,
        "publish_at": publish_at.isoformat(),
        "status": "scheduled",
    }
    if idempotency_key:
        payload["idempotency_key"] = idempotency_key
    return payload
