"""Search surface — Tavily primary → Tavily fallback key → Firecrawl / Exa."""
from __future__ import annotations

from typing import Any

import httpx
import pytest

from agents.lib import search
from agents.lib.search import SearchResult, search_web


class _StubRequest:
    def __init__(self, url: str) -> None:
        self.url = url


def _http_error(status: int) -> httpx.HTTPStatusError:
    return httpx.HTTPStatusError(
        f"{status}",
        request=_StubRequest("https://api.tavily.com/search"),  # type: ignore[arg-type]
        response=httpx.Response(status),
    )


@pytest.mark.asyncio
async def test_tavily_primary_returns_results(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake(*, key: str, query: str, **kw: Any) -> list[SearchResult]:
        assert key == "tvly_fake"
        return [SearchResult(title="t", url="https://x", snippet="s")]

    monkeypatch.setattr(search, "_tavily_call", _fake)

    out = await search_web("hello")
    assert len(out) == 1
    assert out[0].url == "https://x"


@pytest.mark.asyncio
async def test_tavily_primary_429_falls_back_to_secondary_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def _fake(*, key: str, query: str, **kw: Any) -> list[SearchResult]:
        calls.append(key)
        if key == "tvly_fake":
            raise _http_error(429)
        return [SearchResult(title="fallback", url="https://y", snippet="s")]

    monkeypatch.setenv("TAVILY_API_KEY_FALLBACK", "tvly_fallback_fake")
    from agents.lib.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(search, "_tavily_call", _fake)

    out = await search_web("hello")
    assert calls == ["tvly_fake", "tvly_fallback_fake"]
    assert out[0].url == "https://y"
