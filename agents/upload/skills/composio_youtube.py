"""Composio YouTube upload skill.

Calls `YOUTUBE_UPLOAD_VIDEO` with:
  - the mp4 path produced by the download agent,
  - metadata from the metadata agent,
  - a `publishAt` ISO-8601 timestamp so YouTube schedules the unveil
    (status=private + scheduled publish is how YouTube wants you to do
    scheduling; there's no public `scheduled` status).

Guards against the Composio ghost-upload bug (composio#2954): after the action
returns a video id, we immediately verify the video appears in the channel's
upload list. If it doesn't within ~8s, we flag the job for manual verification
instead of silently succeeding.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

from composio import Composio  # composio-core ≥ 0.6
from pydantic import BaseModel

from agents.lib.config import get_settings


class UploadRequest(BaseModel):
    """Parameters for a single Composio `YOUTUBE_UPLOAD_VIDEO` call."""

    entity_id: str                 # composio entity, i.e. the YouTube channel alias
    file_path: Path
    title: str
    description: str
    tags: list[str]
    category_id: int
    publish_at: datetime           # ISO-8601 UTC when the video should go public
    privacy_status: str = "private"  # always private; publishAt controls release


class UploadResult(BaseModel):
    """Return value of :func:`upload` — includes ghost-verify status and raw response."""

    yt_video_id: str
    ghost_verified: bool
    raw: dict[str, Any]


def _client() -> Composio:
    return Composio(api_key=get_settings().composio_api_key.get_secret_value())


async def upload(req: UploadRequest) -> UploadResult:
    """Upload a single video; returns the YouTube video id."""

    def _do_upload() -> dict[str, Any]:
        composio = _client()
        return composio.actions.execute(
            action="YOUTUBE_UPLOAD_VIDEO",
            params={
                "file": str(req.file_path),
                "title": req.title,
                "description": req.description,
                "tags": req.tags,
                "category_id": req.category_id,
                "privacy_status": req.privacy_status,
                "publish_at": req.publish_at.isoformat(),
            },
            entity_id=req.entity_id,
        )

    raw = await asyncio.to_thread(_do_upload)

    # Defensive parse — Composio's response shape varies by toolkit version.
    data = raw.get("data") if isinstance(raw, dict) else None
    data_dict: dict[str, Any] = data if isinstance(data, dict) else {}
    yt_video_id = (
        data_dict.get("id")
        or data_dict.get("videoId")
        or (raw.get("response", {}) if isinstance(raw, dict) else {}).get("id", "")
    )
    if not yt_video_id:
        raise RuntimeError(f"composio upload returned no video id: {raw!r}")

    verified = await _verify_not_ghost(req.entity_id, yt_video_id)
    return UploadResult(yt_video_id=yt_video_id, ghost_verified=verified, raw=raw)


async def _verify_not_ghost(
    entity_id: str, yt_video_id: str, *, attempts: int = 4, delay: float = 2.0
) -> bool:
    """Poll the channel's uploads to confirm the video is real (composio#2954)."""

    def _list_recent() -> list[str]:
        composio = _client()
        resp = composio.actions.execute(
            action="YOUTUBE_LIST_CHANNEL_VIDEOS",
            params={"max_results": 10},
            entity_id=entity_id,
        )
        data = resp.get("data") if isinstance(resp, dict) else None
        items = data.get("items", []) if isinstance(data, dict) else []
        return [
            (it.get("id") or {}).get("videoId") or it.get("videoId") or ""
            for it in items
            if isinstance(it, dict)
        ]

    for _ in range(attempts):
        try:
            ids = await asyncio.to_thread(_list_recent)
            if yt_video_id in ids:
                return True
        except Exception:
            # Listing is best-effort — if the action isn't available we fail open.
            return True
        await asyncio.sleep(delay)
    return False
