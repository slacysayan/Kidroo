"""Orchestrator agent — parses user intent into a structured task plan.

Contract:
    Input  — user's free-text submission + job context (available channels,
             detected source videos).
    Output — TaskPlan: channel_entity_id, schedule, video_ids.

The orchestrator does NOT fan out itself; that's the Hatchet workflow's job
(`workflows.video_pipeline.process_video_batch`). The orchestrator's only
responsibility is turning the user's words into a deterministic plan.
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime

from pydantic import BaseModel, Field, field_validator

from agents.lib.base import BaseAgent
from agents.lib.config import get_settings
from agents.orchestrator.prompts import SYSTEM_PROMPT


class ChannelRef(BaseModel):
    """One connected YouTube channel available to the user."""

    composio_entity_id: str
    name: str


class SourceVideo(BaseModel):
    """A source video detected by the upstream scan step."""

    source_video_id: str
    title: str
    duration_secs: int | None = None


class OrchestratorInput(BaseModel):
    """Input contract for :class:`OrchestratorAgent`."""

    user_message: str
    available_channels: list[ChannelRef]
    detected_videos: list[SourceVideo]


class Schedule(BaseModel):
    """Publish cadence requested by the user."""

    per_day: int = Field(ge=1, le=6)
    start_date: date
    timezone: str = "UTC"
    note: str | None = None


class TaskPlan(BaseModel):
    """Final plan handed to the Hatchet batch workflow."""

    channel_entity_id: str
    schedule: Schedule
    video_ids: list[str]

    @field_validator("video_ids")
    @classmethod
    def _non_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("video_ids must contain at least one id")
        return v


class OrchestratorAgent(BaseAgent[OrchestratorInput, TaskPlan]):
    """Parses a free-text user message into a structured :class:`TaskPlan`."""

    name = "orchestrator"

    async def run(self, inp: OrchestratorInput) -> TaskPlan:
        settings = get_settings()
        if not settings.pipeline_enabled:
            await self.log.error("pipeline kill-switch engaged", reason="PIPELINE_ENABLED=false")
            raise RuntimeError("pipeline is disabled via PIPELINE_ENABLED")

        await self.log.status(
            "parsing user intent",
            n_channels=len(inp.available_channels),
            n_videos=len(inp.detected_videos),
        )
        user_block = _render_user_block(inp)

        buf = ""
        async for delta in self.stream(
            system=SYSTEM_PROMPT,
            user=user_block,
            response_format="json",
            temperature=0.1,
            max_tokens=1024,
        ):
            buf += delta

        try:
            raw = json.loads(buf)
        except json.JSONDecodeError as e:
            await self.log.error("orchestrator JSON parse failed", raw=buf[:500])
            raise ValueError(f"orchestrator produced invalid JSON: {e}") from e

        plan = TaskPlan.model_validate(raw)

        # Post-parse validation — the LLM is free to hallucinate IDs or pick a
        # past start_date, so re-verify every field against the input context
        # before returning the plan.
        today_utc = datetime.now(UTC).date()
        if plan.schedule.start_date < today_utc:
            await self.log.error(
                "orchestrator produced a past start_date",
                start_date=plan.schedule.start_date.isoformat(),
                today_utc=today_utc.isoformat(),
            )
            raise ValueError(
                f"schedule.start_date {plan.schedule.start_date.isoformat()} "
                f"is in the past (today UTC: {today_utc.isoformat()})"
            )

        channel_ids = {c.composio_entity_id for c in inp.available_channels}
        if plan.channel_entity_id not in channel_ids:
            await self.log.error(
                "orchestrator picked an unknown channel",
                channel_entity_id=plan.channel_entity_id,
                available=sorted(channel_ids),
            )
            raise ValueError(
                f"channel_entity_id {plan.channel_entity_id!r} is not in "
                f"available_channels"
            )

        detected_ids = {v.source_video_id for v in inp.detected_videos}
        unknown = [vid for vid in plan.video_ids if vid not in detected_ids]
        if unknown:
            await self.log.error(
                "orchestrator selected videos that were not detected",
                unknown=unknown,
            )
            raise ValueError(
                f"video_ids contains ids not present in detected_videos: {unknown}"
            )

        await self.log.status(
            "task plan ready",
            channel=plan.channel_entity_id,
            per_day=plan.schedule.per_day,
            n_videos=len(plan.video_ids),
        )
        return plan


def _render_user_block(inp: OrchestratorInput) -> str:
    channels = "\n".join(
        f"- {c.composio_entity_id}: {c.name}" for c in inp.available_channels
    )
    videos = "\n".join(
        f"- {v.source_video_id}: {v.title}"
        + (f" ({v.duration_secs}s)" if v.duration_secs else "")
        for v in inp.detected_videos
    )
    return (
        f"User message:\n{inp.user_message}\n\n"
        f"Available channels:\n{channels or '(none)'}\n\n"
        f"Detected source videos:\n{videos or '(none)'}"
    )
