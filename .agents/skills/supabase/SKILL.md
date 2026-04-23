# Skill — Supabase (migrations, RLS, Realtime)

Read this before adding or modifying a Supabase table, column, policy, or realtime publication.

## Prerequisites

- `supabase` CLI installed (SKILLS.sh does this).
- `SUPABASE_URL` and `SUPABASE_DB_URL` in `.env`.

## Migrations

All schema changes go through numbered migration files in `supabase/migrations/`. Never edit a previously applied migration — always add a new one.

### Naming

`NNN_<short_description>.sql` — e.g. `002_add_channel_quota.sql`. Numbers are zero-padded 3 digits, monotonically increasing.

### Applying

```bash
# Option A — Supabase CLI (preferred)
supabase db push

# Option B — direct psql (for Koyeb CI jobs where the Supabase CLI isn't installed)
psql "$SUPABASE_DB_URL" -f supabase/migrations/00X_whatever.sql
```

### Writing a migration

1. Always `create table if not exists` / `alter table ... add column if not exists`.
2. Always define indexes on foreign keys.
3. Every new user-facing table gets an RLS policy restricting rows to `auth.uid() = user_id` (or equivalent join).
4. Every new table that needs live updates gets `alter publication supabase_realtime add table public.<name>;`.
5. Add a `before update` trigger on every table that has `updated_at`.

### Rollback

Supabase does not auto-generate down migrations. If a migration needs to be reverted, write a new migration that undoes it. Do not `git revert` applied migrations.

## Row-Level Security

Every user-facing table is RLS-enabled. Service-role inserts (from the FastAPI server) bypass RLS by default — anon/authenticated clients cannot.

### Canonical pattern

```sql
alter table public.<name> enable row level security;

create policy <name>_owner on public.<name>
    for all using (user_id = auth.uid())
    with check (user_id = auth.uid());
```

For child tables (e.g. `videos` belongs to `jobs`), filter via join:

```sql
create policy videos_owner on public.videos
    for all using (
        exists (select 1 from public.jobs j
                where j.id = videos.job_id and j.user_id = auth.uid())
    );
```

### Testing RLS

```bash
# Impersonate a user from psql and try to read someone else's row
psql "$SUPABASE_DB_URL" <<'EOF'
set role authenticated;
set request.jwt.claims to '{"sub": "<other_user_uuid>"}';
select * from public.jobs;   -- should return 0 rows
EOF
```

## Realtime

- Enabled on `agent_logs`, `videos`, `jobs`.
- The browser subscribes with `postgres_changes` filtered by `job_id=eq.<id>`.
- Do not put large JSON blobs into Realtime-published tables; Supabase has a 2 GB/mo free bandwidth cap. `agent_logs.message` is capped to 2 KB in application code.

## Email allowlist

The magic-link auth allows any email to sign up by default. The allowlist is enforced in two places:

1. **`before_signup` Edge Function** — rejects emails not in the allowlist at signup.
2. **RLS** — a belt-and-braces policy that refuses `select` to any `auth.uid()` whose email is not in the allowlist table.

Both are applied in migration `002_auth_allowlist.sql` (Phase 1).

## Common failures

| Symptom | Fix |
|---|---|
| "permission denied for table X" in the browser | Forgot RLS policy, or policy doesn't match the query filter |
| Realtime subscription returns nothing | Table not added to `supabase_realtime` publication; or filter uses `eq.null` |
| Migration succeeds locally, fails on Supabase | Supabase prod postgres version mismatch — check extensions |

## Related files

- `supabase/migrations/001_initial_schema.sql`
- `docs/ARCHITECTURE.md` — data flow
