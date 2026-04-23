# Skill — adding or modifying a runtime agent

Read this when you are creating a new agent under `agents/` or changing behavior of an existing one.

## Prerequisites

- Read `docs/AGENTS.md` end-to-end.
- Read `agents/lib/base.py`.

## Ground rules

1. Every agent is a subclass of `BaseAgent` and implements `async def run(self, input: AgentInput) -> AgentOutput`.
2. Every agent writes to `agent_logs` via `self.log(step=..., message=..., metadata=...)`. Never call Supabase directly.
3. Every agent that calls an LLM goes through `agents.lib.llm.stream_complete(...)` — never imports `groq` or `cerebras` directly. All LLM calls are streaming; partial tokens flow to `agent_logs` → Supabase Realtime → browser so the user sees the agent think in real time.
4. Every agent that calls an external tool places the tool in its own `skills/` folder (`agents/<name>/skills/<tool>.py`), not inline in `agent.py`.
5. Every agent has a unit test under `tests/unit/agents/test_<name>.py` with mocked LLM + mocked tools.

## Folder layout

```
agents/<name>/
├── __init__.py              # exports <Name>Agent
├── agent.py                 # the BaseAgent subclass
├── prompts.py               # SYSTEM_PROMPT + any user-prompt templates
└── skills/                  # tools this agent can call (if any)
    ├── __init__.py
    └── <tool>.py
```

## Minimal agent skeleton

```python
# agents/<name>/agent.py
from pydantic import BaseModel
from agents.lib.base import BaseAgent
from agents.lib.llm import stream_complete
from agents.<name>.prompts import SYSTEM_PROMPT

class <Name>Input(BaseModel):
    ...

class <Name>Output(BaseModel):
    ...

class <Name>Agent(BaseAgent[<Name>Input, <Name>Output]):
    name = "<name>"

    async def run(self, input: <Name>Input) -> <Name>Output:
        await self.log(step="status", message="started")

        # tool call(s), if any
        await self.log(step="tool_call", message="firecrawl.scrape_url", metadata={"url": input.url})
        raw = await scrape_url(input.url)

        # LLM call — streaming
        await self.log(step="reasoning", message="Extracting niche")
        buf = ""
        async for delta in stream_complete(
            system=SYSTEM_PROMPT,
            user=f"Raw context:\n{raw}",
            response_format="json",
            job_id=self.job_id,
            video_id=self.video_id,
            agent=self.name,
        ):
            buf += delta
            # Partial tokens are auto-flushed to agent_logs by the wrapper.
            # No manual logging needed here.

        await self.log(step="status", message="completed")
        return <Name>Output.model_validate_json(buf)
```

## Adding a new agent — checklist

- [ ] Create `agents/<name>/{__init__.py, agent.py, prompts.py}` and optional `skills/`.
- [ ] Export the class from `agents/__init__.py`.
- [ ] Add a section to `docs/AGENTS.md` with the input/output/tools/prompt.
- [ ] Write `tests/unit/agents/test_<name>.py`.
- [ ] If the agent uses a new external API, add a section to `docs/INTEGRATIONS.md`.

## Modifying an existing agent

- Never change `name` or the shape of `AgentInput` / `AgentOutput` without updating `docs/AGENTS.md` in the same PR.
- Bump the prompt in `prompts.py`, never inline in `agent.py`.
- Add a regression test before modifying behavior.

## Common failures

| Symptom | Fix |
|---|---|
| Agent returns non-JSON and parsing fails | Use `response_format="json"` in `complete()`; tighten the system prompt ("Output ONLY valid JSON") |
| LLM fallback never triggers | Check that your exception classes inherit from `LLMRateLimitError` — `stream_complete()` catches by type, both pre-stream and mid-stream |
| Agent logs show the full response only at the end (no streaming in UI) | Make sure you pass `job_id`, `video_id`, and `agent` to `stream_complete` — the wrapper uses them to insert partial rows |
| `agent_logs` rows missing | You called `self.logger.info(...)` instead of `await self.log(...)` |

## Related files

- `docs/AGENTS.md` — runtime agent specs
- `docs/INTEGRATIONS.md` — external API signatures
- `agents/lib/base.py` — `BaseAgent`
- `agents/lib/llm.py` — Groq/Cerebras failover
- `agents/lib/logging.py` — structured `agent_logs` insertion
