"""JobLogger — emits match the agent_logs schema (step ∈ enum, metadata dict)."""
from __future__ import annotations

from typing import Any

import pytest


class _FakeTable:
    def __init__(self, sink: list[list[dict[str, Any]]]) -> None:
        self._sink = sink
        self._rows: list[dict[str, Any]] = []

    def insert(self, rows: list[dict[str, Any]]) -> _FakeTable:
        self._rows = rows
        return self

    def execute(self) -> Any:
        self._sink.append(self._rows)
        return type("R", (), {"data": self._rows})


class _FakeSupabase:
    def __init__(self) -> None:
        self.inserts: list[list[dict[str, Any]]] = []

    def table(self, _name: str) -> _FakeTable:
        return _FakeTable(self.inserts)


@pytest.mark.asyncio
async def test_joblogger_emits_valid_step_and_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeSupabase()
    from agents.lib import logging as logmod

    monkeypatch.setattr(logmod, "_supabase_server", lambda: fake)

    async with logmod.JobLogger(job_id="j1", video_id=None, agent="research") as log:
        await log.tool_call("tavily.search_web", latency_ms=42)
        await log.reasoning_delta("partial ", provider="groq", partial=True)
        await log.fallback("groq 429", provider_from="groq", provider_to="cerebras")
        await log.error("boom")

    rows = [r for batch in fake.inserts for r in batch]
    # lifecycle start+end add 2 extra rows
    assert len(rows) >= 4
    assert {r["step"] for r in rows} <= {
        "status",
        "tool_call",
        "reasoning",
        "fallback",
        "error",
    }
    assert all("metadata" in r and isinstance(r["metadata"], dict) for r in rows)
    assert all(r["agent"] == "research" for r in rows)
    assert all(r["job_id"] == "j1" for r in rows)
