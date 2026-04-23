"""Upload agent — Composio `YOUTUBE_UPLOAD_VIDEO` with publishAt scheduling.

Also decrements the per-channel quota row on success (channel_quota table)
and enforces idempotency via videos.idempotency_key (sha256(source_video_id +
channel_entity_id)).
"""
from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from agents.lib.base import BaseAgent
from agents.lib.supabase import get_service_client
from agents.upload.skills import composio_youtube


class UploadInput(BaseModel):
    channel_id: str            # public.channels.id (uuid)
    channel_entity_id: str     # composio entity
    source_video_id: str
    file_path: Path
    title: str
    description: str
    tags: list[str]
    category_id: int
    publish_at: datetime


class UploadOutput(BaseModel):
    yt_video_id: str
    ghost_verified: bool
    idempotency_key: str


class UploadAgent(BaseAgent[UploadInput, UploadOutput]):
    name = "upload"

    async def run(self, inp: UploadInput) -> UploadOutput:
        idem = hashlib.sha256(
            f"{inp.source_video_id}::{inp.channel_entity_id}".encode()
        ).hexdigest()

        await self.log.status(
            "upload starting",
            channel_entity_id=inp.channel_entity_id,
            idempotency_key=idem[:16],
        )

        # Idempotency check — if this (source, channel) pair was already uploaded,
        # short-circuit instead of re-uploading.
        existing = await _idempotent_lookup(idem)
        if existing:
            await self.log.status(
                "idempotent hit — skipping re-upload",
                yt_video_id=existing,
                idempotency_key=idem[:16],
            )
            return UploadOutput(
                yt_video_id=existing, ghost_verified=True, idempotency_key=idem
            )

        result = await composio_youtube.upload(
            composio_youtube.UploadRequest(
                entity_id=inp.channel_entity_id,
                file_path=inp.file_path,
                title=inp.title,
                description=inp.description,
                tags=inp.tags,
                category_id=inp.category_id,
                publish_at=inp.publish_at,
            )
        )

        await _decrement_quota(inp.channel_id)

        if not result.ghost_verified:
            await self.log.warning(
                "composio returned a video id but it did not appear in the "
                "channel's recent uploads — flagging for manual verification",
                yt_video_id=result.yt_video_id,
            )
        else:
            await self.log.status(
                "upload scheduled",
                yt_video_id=result.yt_video_id,
                publish_at=inp.publish_at.isoformat(),
            )

        return UploadOutput(
            yt_video_id=result.yt_video_id,
            ghost_verified=result.ghost_verified,
            idempotency_key=idem,
        )


async def _idempotent_lookup(idempotency_key: str) -> str | None:
    def _q() -> str | None:
        supa = get_service_client()
        resp = (
            supa.table("videos")
            .select("yt_video_id")
            .eq("idempotency_key", idempotency_key)
            .not_.is_("yt_video_id", "null")
            .limit(1)
            .execute()
        )
        data = resp.data or []
        if not data:
            return None
        return data[0].get("yt_video_id")

    return await asyncio.to_thread(_q)


async def _decrement_quota(channel_id: str) -> None:
    def _q() -> None:
        supa = get_service_client()
        # Use an RPC or raw SQL for the atomic increment; here we do a
        # read-modify-write that's safe enough for free-tier volumes (<=6/day).
        row = (
            supa.table("channel_quota")
            .select("uploads_today, daily_limit")
            .eq("channel_id", channel_id)
            .limit(1)
            .execute()
        )
        if not row.data:
            supa.table("channel_quota").insert(
                {"channel_id": channel_id, "uploads_today": 1}
            ).execute()
            return
        current = row.data[0].get("uploads_today", 0) or 0
        supa.table("channel_quota").update(
            {"uploads_today": current + 1}
        ).eq("channel_id", channel_id).execute()

    await asyncio.to_thread(_q)
