"""Unified search interface used by the research agent.

Three tiers:
  1. `search_web(query)`    — Tavily (primary key) → Tavily (fallback key)
                              on 429/5xx. Cheapest, fastest, structured.
  2. `deep_scrape(url)`     — Firecrawl when we need the full markdown of a
                              single URL (Tavily snippets are too thin).
  3. `semantic_search(q)`   — Exa for niche / intent-keyword discovery.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx
import structlog
from exa_py import Exa
from firecrawl import FirecrawlApp
from tavily import AsyncTavilyClient

from agents.lib.config import get_settings

_log = structlog.get_logger(__name__)


@dataclass(slots=True)
class SearchResult:
    """A single web-search hit returned by :func:`search_web` / :func:`semantic_search`."""

    title: str
    url: str
    snippet: str
    score: float | None = None
    source: str = ""  # "tavily" | "exa" | "firecrawl"


@dataclass(slots=True)
class ScrapeResult:
    """Result of scraping one URL into clean markdown via :func:`deep_scrape`."""

    url: str
    markdown: str
    title: str | None
    source: str = "firecrawl"


# ─── Tavily ──────────────────────────────────────────────────────────────


async def _tavily_call(
    *,
    key: str,
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
) -> list[SearchResult]:
    """Single Tavily request with a specific API key.

    Separate from `search_web` so tests can monkey-patch the seam cleanly.
    """
    client = AsyncTavilyClient(api_key=key)
    resp = await client.search(
        query=query, max_results=max_results, search_depth=search_depth
    )
    return [
        SearchResult(
            title=r.get("title", ""),
            url=r.get("url", ""),
            snippet=r.get("content", ""),
            score=r.get("score"),
            source="tavily",
        )
        for r in resp.get("results", [])
    ]


async def search_web(
    query: str,
    *,
    max_results: int = 5,
    search_depth: str = "basic",
) -> list[SearchResult]:
    """Search the web via Tavily. Auto-failover to the secondary key on 429/5xx.

    Args:
        query: Free-text query.
        max_results: Number of results.
        search_depth: `"basic"` (fast) or `"advanced"` (deeper, slower).

    Returns:
        List of SearchResult, best-first.

    Raises:
        RuntimeError: Both keys exhausted / network failure.
    """
    settings = get_settings()
    primary = settings.tavily_api_key.get_secret_value()
    fallback = (
        settings.tavily_api_key_fallback.get_secret_value()
        if settings.tavily_api_key_fallback
        else None
    )

    keys = [primary] + ([fallback] if fallback else [])
    last_err: Exception | None = None
    for idx, key in enumerate(keys):
        try:
            results = await _tavily_call(
                key=key,
                query=query,
                max_results=max_results,
                search_depth=search_depth,
            )
            if idx > 0:
                _log.info("tavily.fallback_key_used", query=query)
            return results
        except httpx.HTTPStatusError as e:
            # Only rotate keys for quota / server-side transient failures.
            # Auth / validation errors (4xx except 429) are caller bugs — let
            # them surface immediately instead of burning fallback quota.
            if not _is_retryable_status(e.response.status_code):
                _log.warning(
                    "tavily.non_retryable_http_error",
                    key_index=idx,
                    status=e.response.status_code,
                )
                raise
            last_err = e
            _log.warning(
                "tavily.search_failed",
                key_index=idx,
                status=e.response.status_code,
                will_failover=idx + 1 < len(keys),
            )
            continue
        except (httpx.ConnectError, httpx.ReadTimeout) as e:
            last_err = e
            _log.warning(
                "tavily.search_failed",
                key_index=idx,
                error=str(e),
                will_failover=idx + 1 < len(keys),
            )
            continue

    raise RuntimeError(f"Tavily exhausted (all keys failed): {last_err!r}")


def _is_retryable_status(status: int) -> bool:
    """True for transient HTTP statuses worth rotating keys on."""
    return status == 429 or status >= 500


# ─── Firecrawl ───────────────────────────────────────────────────────────


async def deep_scrape(url: str) -> ScrapeResult:
    """Scrape a single URL into clean markdown via Firecrawl."""
    settings = get_settings()

    def _run() -> ScrapeResult:
        app = FirecrawlApp(api_key=settings.firecrawl_api_key.get_secret_value())
        resp: dict[str, Any] = app.scrape_url(url, params={"formats": ["markdown"]})
        # firecrawl-py v1.x nests the payload under "data" — tolerate either
        # shape so the call keeps working if the SDK unwraps in a later bump.
        payload: dict[str, Any] = resp.get("data") or resp
        md = payload.get("markdown", "") or ""
        metadata = payload.get("metadata") or {}
        title = metadata.get("title")
        return ScrapeResult(url=url, markdown=md, title=title)

    return await asyncio.to_thread(_run)


# ─── Exa ─────────────────────────────────────────────────────────────────


async def semantic_search(query: str, *, num_results: int = 5) -> list[SearchResult]:
    """Semantic (neural) search via Exa — for niche keyword / intent discovery."""
    settings = get_settings()

    def _run() -> list[SearchResult]:
        client = Exa(api_key=settings.exa_api_key.get_secret_value())
        resp = client.search_and_contents(
            query=query,
            num_results=num_results,
            type="neural",
            text={"max_characters": 500},
        )
        return [
            SearchResult(
                title=getattr(r, "title", "") or "",
                url=getattr(r, "url", "") or "",
                snippet=(getattr(r, "text", "") or "")[:500],
                score=getattr(r, "score", None),
                source="exa",
            )
            for r in resp.results
        ]

    return await asyncio.to_thread(_run)
