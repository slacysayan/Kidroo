"""Shared utilities consumed by every runtime agent.

- `config`  — typed `Settings` loaded from env via `pydantic-settings`.
- `logging` — `JobLogger` that writes structured entries to `agent_logs`.
- `llm`     — `stream_complete()` wrapper: Groq primary → Cerebras failover.
- `search`  — unified search interface: Tavily (primary) → Tavily fallback key → Firecrawl / Exa.
- `base`    — `BaseAgent` — every agent subclass inherits from this.
"""

from agents.lib.config import Settings, get_settings
from agents.lib.logging import JobLogger
from agents.lib.llm import LLMUnavailableError, stream_complete
from agents.lib.search import search_web, deep_scrape, semantic_search

__all__ = [
    "BaseAgent",
    "JobLogger",
    "LLMUnavailableError",
    "Settings",
    "deep_scrape",
    "get_settings",
    "search_web",
    "semantic_search",
    "stream_complete",
]

# deferred import to break potential cycles
from agents.lib.base import BaseAgent  # noqa: E402
