# `.agents/` — dev-harness skills

This directory contains **markdown-only** skill files. They document repeatable procedures that any coding agent (Devin, Cursor, Claude Code, Aider, Copilot Workspace) should follow when working in this repo.

These files never import, never execute, and never ship to production. They are reference material.

## When to read a SKILL.md

| Task | Skill |
|---|---|
| First-time repo setup | `skills/setup/SKILL.md` |
| Running tests | `skills/testing/SKILL.md` |
| Adding a Supabase migration or RLS policy | `skills/supabase/SKILL.md` |
| Adding or modifying a runtime agent in `agents/` | `skills/agents-runtime/SKILL.md` |
| Building or modifying frontend UI | `skills/frontend/SKILL.md` |
| Connecting a YouTube channel / debugging OAuth | `skills/composio/SKILL.md` |
| Writing or tuning animations | `skills/gsap/SKILL.md` |
| Writing a Hatchet workflow | `skills/hatchet/SKILL.md` |
| Anything touching secrets, RLS, or ToS | `skills/security/SKILL.md` |

## Authoring a new skill

1. Create `skills/<skill-name>/SKILL.md`.
2. First line: a one-sentence description of when to read this skill.
3. Sections: **Prerequisites**, **Steps**, **Verification**, **Common failures**, **Related files**.
4. Keep it short. If a skill is longer than 3 screens, split it.
5. Add the skill to the table in this README.

## Industry best practice this follows

- [OpenAI `AGENTS.md`](https://github.com/openai/codex/blob/main/AGENTS.md) — root entry file.
- [Cursor Rules](https://docs.cursor.com/context/rules-for-ai) — folder-scoped instruction files.
- [Anthropic Claude Code skills](https://docs.anthropic.com/) — per-task `SKILL.md` files.
- [Devin skills / playbooks](https://docs.devin.ai) — reusable procedure docs.

Keeping one canonical location (`.agents/skills/`) that all of the above agents read means the repo has a **single source of truth** for coding-agent workflows.
