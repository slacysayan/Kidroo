"""Research agent — Tavily (primary) + Firecrawl (deep-scrape) + Exa (semantic).

The research pass produces a JSON brief the Metadata agent consumes. Tavily
snippets usually suffice; Firecrawl fires only when the source URL's content
is the thing we actually need to enrich (e.g. the source description was thin
and the original page has a transcript).
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from agents.lib.base import BaseAgent
from agents.lib.search import SearchResult, deep_scrape, search_web, semantic_search
from agents.research.prompts import SYSTEM_PROMPT


class ResearchInput(BaseModel):
    """Input contract for :class:`ResearchAgent`."""

    source_url: str
    video_title: str
    video_description: str = ""


class ResearchOutput(BaseModel):
    """Structured research brief consumed by :class:`MetadataAgent`."""

    niche: str
    keywords: list[str] = Field(min_length=1)
    trending_angles: list[str] = Field(min_length=1)
    raw_context: str


class ResearchAgent(BaseAgent[ResearchInput, ResearchOutput]):
    """Runs Tavily → Firecrawl → Exa and synthesises a Groq-streamed JSON brief."""

    name = "research"

    async def run(self, inp: ResearchInput) -> ResearchOutput:
        await self.log.status(
            "research started",
            source_url=inp.source_url,
            title=inp.video_title[:120],
        )

        # 1. Tavily — primary web search.
        search_query = _build_query(inp.video_title, inp.video_description)
        tavily_results: list[SearchResult] = []
        try:
            tavily_results = await search_web(search_query, max_results=6)
            await self.log.tool_call(
                "tavily.search_web", n=len(tavily_results), query=search_query
            )
        except Exception as e:
            await self.log.warning("tavily unavailable", error=str(e))

        # 2. Firecrawl — only if Tavily was thin or source description is empty.
        deep_md: str | None = None
        if len(tavily_results) < 3 or len(inp.video_description) < 80:
            try:
                scrape = await deep_scrape(inp.source_url)
                deep_md = scrape.markdown[:4000]
                await self.log.tool_call("firecrawl.deep_scrape", chars=len(deep_md))
            except Exception as e:
                await self.log.warning("firecrawl skipped", error=str(e))

        # 3. Exa — niche + intent discovery.
        exa_results: list[SearchResult] = []
        try:
            exa_results = await semantic_search(
                f"{inp.video_title} trending angles {datetime.now(UTC).year}",
                num_results=5,
            )
            await self.log.tool_call("exa.semantic_search", n=len(exa_results))
        except Exception as e:
            await self.log.warning("exa skipped", error=str(e))

        # 4. Groq (streaming) — synthesize brief.
        user_block = _render_user_block(
            inp, tavily_results, exa_results, deep_md
        )
        buf = ""
        async for delta in self.stream(
            system=SYSTEM_PROMPT,
            user=user_block,
            response_format="json",
            temperature=0.3,
            max_tokens=1200,
        ):
            buf += delta

        try:
            raw = json.loads(buf)
        except json.JSONDecodeError as e:
            await self.log.error("research JSON parse failed", raw=buf[:500])
            raise ValueError(f"research produced invalid JSON: {e}") from e

        out = ResearchOutput.model_validate(raw)
        await self.log.status(
            "research complete",
            niche=out.niche,
            n_keywords=len(out.keywords),
            n_angles=len(out.trending_angles),
        )
        return out


def _build_query(title: str, description: str) -> str:
    base = title.strip()
    if description:
        # first 160 chars of description, compressed
        base += " — " + " ".join(description.split())[:160]
    return base


def _render_user_block(
    inp: ResearchInput,
    tavily: list[SearchResult],
    exa: list[SearchResult],
    deep_md: str | None,
) -> str:
    parts: list[str] = [
        f"Source URL: {inp.source_url}",
        f"Video title: {inp.video_title}",
        f"Video description:\n{inp.video_description or '(empty)'}",
    ]
    if tavily:
        parts.append(
            "Tavily search results:\n"
            + "\n".join(
                f"- [{r.title}]({r.url}) — {r.snippet[:200]}" for r in tavily
            )
        )
    if exa:
        parts.append(
            "Exa semantic results:\n"
            + "\n".join(
                f"- [{r.title}]({r.url}) — {r.snippet[:200]}" for r in exa
            )
        )
    if deep_md:
        parts.append(f"Deep-scrape (source page, truncated):\n{deep_md}")
    return "\n\n".join(parts)
