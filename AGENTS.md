# AGENTS.md — entry spec for coding agents

This file is the root instruction for any coding agent (Devin, Cursor, Claude Code, Aider, Copilot Workspace, etc.) working in this repository. **Read this first. Then read `README.md`. Then proceed.**

---

## What this repo is

Kidroo is an agentic YouTube content pipeline. Five specialized runtime AI agents (orchestrator, research, metadata, download, upload) coordinate to turn a pasted YouTube URL into a scheduled upload on an owned YouTube channel.

There are **two kinds of agents** in this repo. Do not confuse them.

| Kind | Location | Ships to prod? | Purpose |
|---|---|---|---|
| **Runtime agents** | `agents/` | Yes | CrewAI agents that execute the pipeline (orchestrator, research, metadata, download, upload) |
| **Dev-harness agents / skills** | `.agents/` | No | Markdown skill docs read by coding agents (like you) to know how to work in this repo |

When a human or docs says "add a new agent", they mean a **runtime agent** in `agents/`. When they say "add a skill", they mean a **dev-harness skill** in `.agents/skills/<skill-name>/SKILL.md`.

---

## Ground rules for coding agents

1. **Read before you write.** Always read `README.md`, the relevant file in `docs/`, and any matching `.agents/skills/*/SKILL.md` before making changes.
2. **Minimal, focused edits.** Scope every PR to one concern. Do not refactor adjacent code.
3. **Follow the spec.** When a doc in `docs/` specifies a function signature, data shape, or prompt, match it exactly. If the spec looks wrong, update the spec in the same PR — do not silently deviate.
4. **Never hard-code secrets.** Read from environment variables declared in `.env.example`.
5. **Do not modify runtime code from `.agents/`.** Dev-harness skills never import from `agents/`.
6. **Agents log every step.** Any new runtime step must insert a row into `agent_logs` with `{job_id, video_id, agent, step, message, metadata}`.
7. **All public Python is typed.** `mypy --strict` must pass. No `Any`, `getattr`, or `setattr` unless unavoidable and commented.
8. **All public TS is typed.** `tsc --noEmit` must pass. No `any`.
9. **Prefer existing skills.** If a skill exists for what you are doing (`.agents/skills/<skill>/SKILL.md`), follow it. Do not improvise.
10. **Write tests.** New runtime code gets a unit test in `tests/unit/`. New integrations get a recorded-response integration test in `tests/integration/`.

---

## File map — where does X live?

| I want to… | Go here |
|---|---|
| Understand the product | `docs/PRD.md` |
| Understand the system | `docs/ARCHITECTURE.md` + `README.md#system-canvas` |
| Understand a runtime agent | `docs/AGENTS.md` (runtime specs) + `agents/<name>/` |
| Add/modify a runtime agent | `.agents/skills/agents-runtime/SKILL.md` |
| Call an external API | `docs/INTEGRATIONS.md` |
| Build UI | `docs/UI_SPEC.md` + `.agents/skills/frontend/SKILL.md` |
| Animate UI | `.agents/skills/gsap/SKILL.md` |
| Add a Supabase table or column | `.agents/skills/supabase/SKILL.md` |
| Write a Hatchet workflow | `.agents/skills/hatchet/SKILL.md` |
| Connect a new YouTube channel | `.agents/skills/composio/SKILL.md` |
| Run tests | `.agents/skills/testing/SKILL.md` |
| Know which libraries to use | `docs/TECH_STACK.md` |
| Plan the next feature | `docs/ROADMAP.md` |

---

## Conventions

### Python (`agents/`, `apps/api/`, `workflows/`)

- Python 3.11.
- Package manager: **uv**. Dependencies declared in `pyproject.toml`, locked in `uv.lock`.
- Formatter: **ruff format**. Linter: **ruff check**. Type checker: **mypy --strict**.
- Async by default. Use `asyncio`, not threads.
- No `print()` in runtime code. Use the `structlog`-backed logger exported from `agents.lib.logging`.
- Every public function has a docstring and full type annotations.

### TypeScript (`apps/web/`)

- Node 20+, Next.js 15 App Router, React 19.
- Package manager: **pnpm**. Workspace: **Turborepo**.
- Formatter + linter: **Biome**.
- Type checker: **tsc --noEmit** (strict mode).
- No default exports except for Next.js page/layout files.
- No client-side fetch of Supabase service-role keys. Server-only operations go through FastAPI.

### Git

- Branch naming: `devin/<timestamp>-<short-description>` (timestamps prevent collisions with concurrent agents).
- Commits: conventional-commit style (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).
- No force-push to `main`. Force-push on your feature branch is OK only with `--force-with-lease`.
- No direct commits to `main`. Every change goes through a PR.
- Pre-commit hooks run `ruff`, `biome`, and a secret-scan (see `.agents/skills/setup/SKILL.md`).

---

## Runtime-agent contract (the five agents)

Every runtime agent in `agents/<name>/agent.py` exposes:

```python
from agents.lib.base import BaseAgent, AgentInput, AgentOutput

class <Name>Agent(BaseAgent):
    name: str = "<name>"              # must match folder name

    async def run(self, input: AgentInput) -> AgentOutput:
        ...
```

And writes an `agent_logs` row at these moments:

| When | `step` value | `message` example |
|---|---|---|
| Agent starts | `"status"` | `"started"` |
| Tool call begins | `"tool_call"` | `"firecrawl.scrape_url(url=...)"` |
| LLM reasoning output | `"reasoning"` | `"Decided niche: consumer tech"` |
| LLM fallback fires | `"fallback"` | `"Groq 429 → Cerebras"` |
| Agent finishes | `"status"` | `"completed"` |
| Agent errors | `"error"` | `"yt-dlp exited 1: ..."` |

See [`docs/AGENTS.md`](docs/AGENTS.md) for the full per-agent specification (input shape, output shape, prompts, tools, logging).

---

## When in doubt

1. Check `docs/` and `.agents/skills/` for a relevant spec.
2. If none exists, **create it in the same PR** as your code change. A feature without a spec is a feature that will break.
3. If still unsure, leave a PR comment tagging `@slacysayan` — do not guess at product intent.
