# Skill — security, secrets, RLS, YouTube ToS

Read this before touching anything that involves credentials, user data, or third-party content.

## Secrets

- **Never commit a secret.** `.env` is gitignored. `.env.example` is the only tracked file and contains placeholder values only.
- **Never log a secret.** `structlog` is configured to redact keys matching `/(?i)(key|token|secret|password)/` before any log line leaves the process.
- **Never embed secrets in error messages returned to the browser.** FastAPI returns a generic `500` with a request ID; the real error goes to structured logs only.
- **Rotate secrets quarterly** (Groq, Cerebras, Firecrawl, Exa, Composio, Supabase service key, Hatchet token). Supabase anon key does not need rotation unless compromised.

### Secret-scan pre-commit

`gitleaks` runs as a pre-commit hook. If it blocks your commit, **do not bypass** with `--no-verify`. Remove the secret and rotate it immediately.

## Supabase RLS

- Every user-facing table has RLS enabled.
- The service-role key bypasses RLS by design — only use it from the FastAPI server, never from the browser.
- When adding a table, always add the canonical owner policy (see `.agents/skills/supabase/SKILL.md`).
- Test RLS with a psql impersonation check before shipping.

## Auth allowlist

Kidroo is a private internal tool. Supabase Auth (email+password / magic link / OAuth) sign-up must be restricted to an email allowlist:

1. `auth.users.email` is validated against the `public.allowed_emails` table by a `before_signup` Edge Function.
2. Belt-and-braces: a `select` RLS policy on every user-facing table also verifies the email is allowlisted.

Both layers ship in migration `002_auth_allowlist.sql` (Phase 1).

## YouTube ToS & Content ID

This is the biggest non-technical risk in the product. Be honest about it.

### What the tool can do

Upload any source video to any channel the user has connected via Composio.

### What that means legally

- **Copyright.** Re-uploading a video you do not own is copyright infringement unless you have an explicit license (written) or it falls under fair use (transformative, commentary, critique). "It was public on YouTube" is not a license.
- **Content ID.** Third-party content uploaded to your channel will likely be detected within hours. Consequences range from revenue redirect → muting → blocking → strike. Three strikes terminates the channel.
- **Automated action.** YouTube's ToS prohibits "automated access" that circumvents the intended use of the service. A tool that scrapes + re-uploads at scale is plainly within the policy's concern.

### Mitigations the product provides

- **Confirmation step.** The user must explicitly select videos and target channel in the chat — no auto-upload without user action.
- **Channel isolation.** One Composio entity per channel ensures a strike on one channel cannot cascade.
- **Audit log.** Every upload is logged with source URL, target channel, and responsible user — `agent_logs` + `videos`.
- **Kill switch.** `PIPELINE_ENABLED=false` globally halts new uploads.

### What the product does NOT do

- We do not bypass Content ID.
- We do not hide the source.
- We do not ship to public users or commercial customers at this time.

### Developer responsibilities

If you add a feature that expands the attack surface (e.g. auto-upload triggers, bulk imports from third-party sites, Shorts auto-generation), **add a matching section to this skill and the README risk register** in the same PR.

## /tmp and staging files

- Downloaded videos are staged under `/tmp/kidroo/<job_id>/<video_id>.mp4`.
- Railway containers (and any other PaaS we deploy on) are ephemeral — `/tmp` evaporates on restart. That is fine because Hatchet resumes from the last checkpoint (re-downloads if necessary).
- **Always** delete the staged file on upload success, on upload failure, and on job cancellation.
- `/tmp/kidroo/` is purged on worker boot.

## Related files

- `docs/INTEGRATIONS.md` — Composio ghost-upload risk + mitigations
- `.agents/skills/supabase/SKILL.md` — RLS patterns
- `.agents/skills/composio/SKILL.md` — OAuth + upload handling
- `README.md#risks--open-items` — full risk register
