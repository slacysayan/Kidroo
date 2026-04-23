# Tech stack — every library, every version, every reason

Pinned versions live in `pyproject.toml` (Python) and `package.json` (JS). This doc explains **why** each choice was made and what it replaced.

## Frontend

| Package | Version (floor) | Role | Why this over alternatives |
|---|---|---|---|
| `next` | `^15` | React framework | App Router, Vercel-native, edge runtime. Replaces Remix (less mature agent docs). |
| `react` | `^19` | UI library | Latest stable, server components. |
| `tailwindcss` | `^4` | Styling | shadcn dependency. v4 moves config to CSS, zero-runtime. |
| `shadcn/ui` | pinned via CLI | Component kit | Copy-paste; owned code. Replaces MUI (black box) and Mantine (opinionated styling). |
| `gsap` | `^3.12` | Primary animation | Timeline-based, professional control. Chosen over Anime.js for ecosystem + Flip plugin. |
| `framer-motion` | `^11` | shadcn-native animation | Already used by Radix entrances. Kept narrow. |
| `geist` | `^1.3` | Typography | Vercel's free font. Free alternative to Inter + JetBrains Mono. |
| `lucide-react` | `^0.400` | Icons | shadcn default; tree-shakeable. |
| `@supabase/supabase-js` | `^2` | DB + Realtime + Auth | Canonical SDK. |
| `biome` | `^1.9` | Lint + format | Replaces eslint + prettier. One tool, faster. |

## Backend

| Package | Version (floor) | Role | Why |
|---|---|---|---|
| `python` | `3.11` | Runtime | CrewAI + Hatchet both target 3.11. |
| `fastapi` | `^0.115` | HTTP server | Async, typed, OpenAPI schema auto-generated. |
| `uvicorn[standard]` | `^0.32` | ASGI server | FastAPI canonical. |
| `pydantic` | `^2.9` | Schemas | FastAPI + CrewAI dependency. |
| `crewai` | `^0.80` | Agent framework | Multi-agent, tool-calling, native async. Chosen over raw LangChain (too heavy) and AutoGen (harder to ship). |
| `hatchet-sdk` | `^1.0` | Durable workflows | Python-native, Postgres-backed. Replaces Trigger.dev (TypeScript-only). |
| `groq` | `^0.11` | Primary LLM | OpenAI-compatible. |
| `cerebras-cloud-sdk` | `^1.0` | Fallback LLM | OpenAI-compatible. |
| `firecrawl-py` | `^1.8` | Web scraping | Canonical SDK. |
| `exa-py` | `^1.0` | Semantic search | Canonical SDK. |
| `composio` | `^0.7` | YouTube OAuth + actions | Canonical SDK. |
| `supabase` | `^2.8` | DB + Realtime + Auth | Server-side. |
| `structlog` | `^24` | Structured logging | JSON logs with `trace_id`/`span_id`. |
| `yt-dlp` | latest | Download + scan | Installed as a CLI tool via `uv tool install yt-dlp`. |

## Dev & CI

| Package | Role |
|---|---|
| `uv` | Python package + project mgr |
| `ruff` | Python format + lint (replaces black + flake8 + isort) |
| `mypy` | Python type checking (`--strict`) |
| `pytest` + `pytest-asyncio` + `pytest-recording` | Testing; VCR for integration tests |
| `pnpm` | JS package mgr (replaces npm/yarn) |
| `turbo` | Monorepo task runner (replaces nx) |
| `biome` | JS format + lint + import sort |
| `vitest` | Unit testing (replaces jest) |
| `playwright` | E2E testing |
| `pre-commit` | Git hooks |
| `gitleaks` | Secret scanning |

## What was removed from the original PRD and why

| Removed | Replaced by | Reason |
|---|---|---|
| Trigger.dev | Hatchet | Trigger.dev has no Python SDK. |
| LangChain | CrewAI native LLM config | Redundant abstraction layer over CrewAI. |
| Railway | Koyeb free | Railway's free tier was discontinued. |
| FastAPI WebSocket streaming | Supabase Realtime only | Two realtime channels were redundant. |
| ESLint + Prettier | Biome | Single tool, 100× faster. |
| Jest | Vitest | Native ESM, same API, faster. |
| npm/yarn | pnpm | Content-addressable store, correct hoisting. |
| Poetry | uv | 10–100× faster, official Python-packaging endorsed. |
