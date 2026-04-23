"""Metadata agent — turns a research brief into upload-ready metadata."""
from __future__ import annotations

import json
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from agents.lib.base import BaseAgent
from agents.metadata.prompts import SYSTEM_PROMPT
from agents.research.agent import ResearchOutput


class MetadataInput(BaseModel):
    research: ResearchOutput
    video_title: str
    duration_secs: int
    publish_at: datetime


class MetadataOutput(BaseModel):
    title: str = Field(max_length=60)
    description: str
    tags: list[str] = Field(min_length=1, max_length=30)
    hashtags: list[str] = Field(min_length=1, max_length=5)
    category_id: int
    publish_at: datetime

    @field_validator("tags")
    @classmethod
    def _lowercase_tags(cls, v: list[str]) -> list[str]:
        return [t.lower().strip().lstrip("#") for t in v if t.strip()]

    @field_validator("hashtags")
    @classmethod
    def _hashtag_prefix(cls, v: list[str]) -> list[str]:
        return [h if h.startswith("#") else f"#{h}" for h in v]


class MetadataAgent(BaseAgent[MetadataInput, MetadataOutput]):
    name = "metadata"

    async def run(self, inp: MetadataInput) -> MetadataOutput:
        await self.log.status(
            "generating metadata",
            niche=inp.research.niche,
            duration_secs=inp.duration_secs,
        )

        user_block = (
            f"Research brief:\n{inp.research.model_dump_json(indent=2)}\n\n"
            f"Video title (source): {inp.video_title}\n"
            f"Duration (seconds): {inp.duration_secs}\n"
            f"publish_at: {inp.publish_at.isoformat()}\n"
        )

        buf = ""
        async for delta in self.stream(
            system=SYSTEM_PROMPT,
            user=user_block,
            response_format="json",
            temperature=0.4,
            max_tokens=1500,
        ):
            buf += delta

        try:
            raw = json.loads(buf)
        except json.JSONDecodeError as e:
            await self.log.error("metadata JSON parse failed", raw=buf[:500])
            raise ValueError(f"metadata produced invalid JSON: {e}") from e

        out = MetadataOutput.model_validate(raw)
        await self.log.status(
            "metadata ready",
            title=out.title,
            n_tags=len(out.tags),
            category_id=out.category_id,
        )
        return out
