# Skill — repository setup

Read this when you are setting up Kidroo for the first time or onboarding a new contributor.

## Prerequisites

- Git.
- Linux or macOS. Windows is unsupported (yt-dlp + ffmpeg dev paths untested).
- A working internet connection (installers fetch from Astral, fnm, Composio).

## Steps

1. Clone the repo and run the bootstrap installer:
   ```bash
   git clone https://github.com/slacysayan/Kidroo.git
   cd Kidroo
   ./SKILLS.sh
   ```
   The script installs `uv`, Python 3.11, `fnm`, Node 20, `pnpm`, `yt-dlp`, the Composio CLI, and the Supabase CLI. It is idempotent — safe to re-run.

2. Copy the env template and fill in secrets:
   ```bash
   cp .env.example .env
   # open .env and fill every key. Inline comments document each one.
   ```
   You will need accounts at: Groq, Cerebras, Firecrawl, Exa, Composio, Supabase, and Hatchet. All offer free tiers.

3. Apply the Supabase migration:
   ```bash
   supabase db push                                                        # if using Supabase CLI
   # OR
   psql "$SUPABASE_DB_URL" -f supabase/migrations/001_initial_schema.sql   # direct psql
   ```
   Then confirm Realtime is enabled on `agent_logs` via the Supabase dashboard (Database → Replication).

4. Connect your first YouTube channel via Composio:
   ```bash
   composio connections create --toolkit YOUTUBE --user-id finance_daily
   ```
   Follow the OAuth redirect. On return, insert a row into `public.channels`:
   ```sql
   insert into public.channels (user_id, name, composio_entity_id, connected)
   values (auth.uid(), 'Finance Daily', 'finance_daily', true);
   ```

5. Install pre-commit hooks (idempotent):
   ```bash
   pre-commit install
   ```

6. Run the dev servers:
   ```bash
   pnpm dev                               # Next.js via Turborepo
   uv run fastapi dev apps/api/main.py    # FastAPI
   uv run python -m workflows.worker      # Hatchet worker (separate terminal)
   ```

## Verification

Open http://localhost:3000 and sign in via email + password (or magic link, or Google OAuth — any flow is wired). The sidebar should list your one connected channel (`finance_daily`). An empty "No jobs yet" state should render in the chat pane.

## Common failures

| Symptom | Fix |
|---|---|
| `uv: command not found` after running SKILLS.sh | `export PATH="$HOME/.local/bin:$PATH"` and re-run |
| `supabase db push` fails with "project not linked" | `supabase link --project-ref <ref>` then retry |
| Magic-link or confirmation email never arrives | Check Supabase email provider config; for dev, use `http://localhost:54321/inbucket`. For email+password signups, verify email confirmation is enabled/disabled to match your flow. |
| Composio OAuth opens a blank page | Check `COMPOSIO_API_KEY` and that the toolkit is enabled in the Composio dashboard |

## Related files

- `SKILLS.sh` — installer
- `.env.example` — every env var with inline docs
- `supabase/migrations/001_initial_schema.sql`
- `.agents/skills/composio/SKILL.md` — channel-connection deep dive
