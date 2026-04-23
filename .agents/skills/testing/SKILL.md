# Skill — testing

Read this before running or writing tests.

## Prerequisites

- Repo bootstrapped per `.agents/skills/setup/SKILL.md`.
- `.env` populated with at minimum `SUPABASE_*` + `GROQ_API_KEY`.

## Test tiers

| Tier | Runner | Location | Speed | What it covers |
|---|---|---|---|---|
| Unit | `pytest` / `vitest` | `tests/unit/`, `apps/web/**/*.test.ts` | <1 s per test | Pure functions, agents with mocked LLMs |
| Integration | `pytest --record-mode=once` (VCR) | `tests/integration/` | ~10 s per test | Real external APIs with recorded cassettes |
| E2E | `playwright` | `tests/e2e/` | ~30 s per test | Full browser flow against a running stack |

## Commands

```bash
# Python
uv run pytest                              # all unit + integration tests
uv run pytest tests/unit -x                # unit only, fail-fast
uv run pytest --record-mode=rewrite        # re-record VCR cassettes (requires live keys)
uv run mypy --strict agents apps/api workflows
uv run ruff check .
uv run ruff format --check .

# JavaScript
pnpm test                                  # vitest (unit)
pnpm typecheck                             # tsc --noEmit
pnpm lint                                  # biome check
pnpm e2e                                   # playwright

# Everything at once (CI parity)
pnpm check                                 # runs all the above via Turborepo
```

## Writing a new runtime-agent unit test

Mock the LLM and the tool calls. The agent should never hit the network in a unit test.

```python
# tests/unit/agents/test_metadata.py
import pytest
from agents.metadata.agent import MetadataAgent

@pytest.mark.asyncio
async def test_metadata_agent_returns_valid_json(monkeypatch):
    monkeypatch.setattr(
        "agents.lib.llm.complete",
        mock_llm_returning({"title": "T", "description": "D", "tags": [...], ...}),
    )
    agent = MetadataAgent()
    out = await agent.run(AgentInput(...))
    assert out.title == "T"
    assert len(out.tags) == 15
```

## Writing a new integration test

Use VCR via `pytest-recording`. The first run records real HTTP; subsequent runs replay the cassette. **Redact secrets** using `filter_headers` and `before_record_request`:

```python
# tests/integration/conftest.py
import pytest

@pytest.fixture(scope="module")
def vcr_config():
    return {
        "filter_headers": ["authorization", "x-api-key"],
        "before_record_request": redact_query_string(["api_key"]),
    }

# tests/integration/test_firecrawl.py
@pytest.mark.vcr
async def test_firecrawl_scrapes_mkbhd():
    from agents.research.skills.firecrawl_scrape import scrape
    out = await scrape("https://www.youtube.com/@mkbhd")
    assert "MKBHD" in out.markdown
```

Commit cassettes under `tests/integration/cassettes/`.

## Verification

A successful CI run requires:
- `ruff check .` — 0 errors
- `ruff format --check .` — 0 diffs
- `mypy --strict` — 0 errors
- `pytest` — all green
- `pnpm typecheck` — 0 errors
- `pnpm lint` — 0 errors
- `pnpm test` — all green

## Common failures

| Symptom | Fix |
|---|---|
| VCR test fails on CI but passes locally | Cassette was recorded against a different API response — rerun `--record-mode=rewrite` locally and commit |
| `mypy` complains about `crewai` types | Add the module to `[tool.mypy.overrides]` in `pyproject.toml` with `ignore_missing_imports = true` |
| Playwright can't find a running server | Ensure `pnpm dev` is up; for CI use `playwright test --webServer` config |

## Related files

- `pyproject.toml` — `[tool.pytest.ini_options]`, `[tool.mypy]`, `[tool.ruff]`
- `biome.json` — JS lint + format config
- `.github/workflows/ci.yml` — CI parity (added in Phase 5)
