"""Research-agent tool: Tavily web search.

Primary search surface for the research agent. Wraps `agents.lib.search.search_web`
and shapes the result for the agent's prompt template.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from agents.lib.search import SearchResult, search_web


class TavilySearchInput(BaseModel):
    query: str = Field(description="Free-text query, English preferred.")
    max_results: int = Field(default=5, ge=1, le=10)
    search_depth: str = Field(
        default="basic",
        description='"basic" (fast) or "advanced" (deeper, slower)',
    )


class TavilySearchOutput(BaseModel):
    query: str
    results: list[SearchResult]


async def tavily_search(inp: TavilySearchInput) -> TavilySearchOutput:
    """Run a Tavily search. Auto-fails over to the secondary Tavily key on 429/5xx."""
    results = await search_web(
        inp.query,
        max_results=inp.max_results,
        search_depth=inp.search_depth,
    )
    return TavilySearchOutput(query=inp.query, results=results)
