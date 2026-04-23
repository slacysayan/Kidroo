# `tests/`

Three tiers — see [`.agents/skills/testing/SKILL.md`](../.agents/skills/testing/SKILL.md).

- `unit/` — pytest / vitest. Pure functions, mocked LLMs, mocked tools.
- `integration/` — pytest with VCR cassettes against real external APIs.
- `e2e/` — Playwright against a running stack.
