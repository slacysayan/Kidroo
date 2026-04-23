"""Pytest fixtures: env isolation + fake logger."""
from __future__ import annotations

from typing import Any

import pytest

_FAKE_ENV = {
    "GROQ_API_KEY": "gsk_fake",
    "CEREBRAS_API_KEY": "csk_fake",
    "TAVILY_API_KEY": "tvly_fake",
    "FIRECRAWL_API_KEY": "fc_fake",
    "EXA_API_KEY": "exa_fake",
    "COMPOSIO_API_KEY": "ak_fake",
    "SUPABASE_URL": "https://fake.supabase.co",
    "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_fake",
    "SUPABASE_SECRET_KEY": "sb_secret_fake",
    "SUPABASE_DB_URL": "postgresql://u:p@localhost:5432/postgres",
    "HATCHET_CLIENT_TOKEN": "hatchet_fake",
    "PIPELINE_ENABLED": "true",
}


@pytest.fixture(autouse=True)
def _fake_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in _FAKE_ENV.items():
        monkeypatch.setenv(k, v)
    # clear settings cache across tests
    from agents.lib.config import get_settings

    get_settings.cache_clear()


class FakeLogger:
    """Minimal JobLogger substitute that records every emit."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict[str, Any]]] = []
        self.trace_id = "00000000-0000-0000-0000-000000000000"

    async def status(self, message: str, **meta: Any) -> None:
        self.events.append(("status", message, meta))

    async def tool_call(self, tool: str, **meta: Any) -> None:
        self.events.append(("tool_call", tool, meta))

    async def reasoning_delta(self, text: str, **meta: Any) -> None:
        self.events.append(("reasoning", text, meta))

    async def fallback(self, reason: str, **meta: Any) -> None:
        self.events.append(("fallback", reason, meta))

    async def warning(self, message: str, **meta: Any) -> None:
        self.events.append(("warning", message, meta))

    async def error(self, message: str, **meta: Any) -> None:
        self.events.append(("error", message, meta))

    async def info(self, message: str, **meta: Any) -> None:
        self.events.append(("status", message, meta))


@pytest.fixture
def fake_logger() -> FakeLogger:
    return FakeLogger()
