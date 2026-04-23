"""Streaming LLM wrapper — failover + partial-token flush semantics."""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from agents.lib import llm
from agents.lib.llm import LLMUnavailableError, stream_complete
from tests.conftest import FakeLogger


async def _collect(it: AsyncIterator[str]) -> str:
    buf = ""
    async for d in it:
        buf += d
    return buf


@pytest.mark.asyncio
async def test_happy_path_groq(monkeypatch: pytest.MonkeyPatch, fake_logger: FakeLogger) -> None:
    async def _fake_groq(**kw: Any) -> AsyncIterator[str]:
        for tok in ["Hel", "lo ", "world"]:
            yield tok

    monkeypatch.setattr(llm, "_groq_stream", _fake_groq)

    out = await _collect(stream_complete(system="s", user="u", logger=fake_logger))  # type: ignore[arg-type]
    assert out == "Hello world"
    # No fallback
    assert not any(kind == "fallback" for kind, *_ in fake_logger.events)


@pytest.mark.asyncio
async def test_pre_stream_failover(
    monkeypatch: pytest.MonkeyPatch, fake_logger: FakeLogger
) -> None:
    async def _boom(**kw: Any) -> AsyncIterator[str]:
        raise RuntimeError("429: rate limit")
        yield ""  # pragma: no cover — make this a generator

    async def _ok_cerebras(**kw: Any) -> AsyncIterator[str]:
        assert kw.get("assistant_prefix") in (None, "")
        for tok in ["ok-", "from-", "cerebras"]:
            yield tok

    monkeypatch.setattr(llm, "_groq_stream", _boom)
    monkeypatch.setattr(llm, "_cerebras_stream", _ok_cerebras)

    out = await _collect(stream_complete(system="s", user="u", logger=fake_logger))  # type: ignore[arg-type]
    assert out == "ok-from-cerebras"
    kinds = [k for k, *_ in fake_logger.events]
    assert "fallback" in kinds


@pytest.mark.asyncio
async def test_mid_stream_failover_preserves_prefix(
    monkeypatch: pytest.MonkeyPatch, fake_logger: FakeLogger
) -> None:
    async def _groq_partial(**kw: Any) -> AsyncIterator[str]:
        yield "Partial "
        yield "tokens "
        raise RuntimeError("stream dropped")

    seen: dict[str, str | None] = {}

    async def _cerebras_continues(*, assistant_prefix: str | None, **kw: Any) -> AsyncIterator[str]:
        seen["prefix"] = assistant_prefix
        yield "continue."

    monkeypatch.setattr(llm, "_groq_stream", _groq_partial)
    monkeypatch.setattr(llm, "_cerebras_stream", _cerebras_continues)

    out = await _collect(stream_complete(system="s", user="u", logger=fake_logger))  # type: ignore[arg-type]
    assert out == "Partial tokens continue."
    assert seen["prefix"] == "Partial tokens "


@pytest.mark.asyncio
async def test_both_providers_fail(
    monkeypatch: pytest.MonkeyPatch, fake_logger: FakeLogger
) -> None:
    async def _boom(**kw: Any) -> AsyncIterator[str]:
        raise RuntimeError("boom")
        yield ""  # pragma: no cover

    monkeypatch.setattr(llm, "_groq_stream", _boom)
    monkeypatch.setattr(llm, "_cerebras_stream", _boom)

    with pytest.raises(LLMUnavailableError):
        await _collect(stream_complete(system="s", user="u", logger=fake_logger))  # type: ignore[arg-type]
