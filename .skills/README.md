# `.skills/` — third-party agent-skill manifest

This directory pins the **external** agent skills (from [skills.sh](https://skills.sh)) that this repo depends on. These are reference skills authored by the tool vendors themselves (Supabase, Composio, Firecrawl, shadcn, GSAP, Vercel Labs, etc.) — the authoritative "how to use X" procedure from the people who ship X.

They are complementary to `.agents/skills/`:

| Directory | Contents | Source of truth | Updated by |
|---|---|---|---|
| `.agents/skills/` | Repo-specific procedures written in-house (setup, testing, RLS patterns **for this repo**, hatchet workflows **for this repo**, etc.) | Us | Human authors + PRs |
| `.skills/` | Upstream vendor skills installed via `npx skills add` | The vendor (Supabase, Composio, etc.) | `./SKILLS.sh --skills-install` |

## Manifest

`manifest.json` is the single source of truth for which external skills are installed. Every entry is a `{ source, skill, why, group }` tuple that documents **what** is installed and **why** it was chosen.

## Installing / updating

```bash
./SKILLS.sh --skills-install       # install every entry in manifest.json
./SKILLS.sh --skills-update        # run `npx skills check` + `npx skills update`
./SKILLS.sh --skills-find <query>  # search skills.sh for more skills to add
```

Newly added skills land under whatever directory the `skills` CLI chooses (typically `.claude/skills/<skill>` or `~/.skills/…` depending on the agent's convention). Commit them to the repo if the skill contains bundled scripts/resources we want pinned; otherwise the manifest alone is enough — reproducible installs are driven from `manifest.json`.

## When to add a new skill

- A new external tool is introduced (Pinecone, Redis, Stripe, etc.).
- A major version of an existing tool changes the recommended patterns.
- A teammate finds a higher-quality skill than the one currently listed.

In every case: update `manifest.json` with a non-empty `why`, then re-run `./SKILLS.sh --skills-install`.
