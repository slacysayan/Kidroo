-- 003: defaults + atomic quota helper for production safety.
--
-- 1. `jobs.user_id` gets a `default auth.uid()` so browser-side inserts
--    through RLS (e.g. `JobComposer`) no longer need to spell out the
--    user id — Supabase fills it in from the JWT. The existing RLS
--    with-check policy still enforces `user_id = auth.uid()`.
--
-- 2. `increment_uploads_today(p_channel_id uuid)` — atomic upsert /
--    increment of `channel_quota.uploads_today`. Replaces the
--    read-modify-write in `_decrement_quota` that could lose increments
--    when several uploads for the same channel finish concurrently
--    (fan-out allows up to 6 per user).

-- 1. Default jobs.user_id to the authenticated user.
alter table public.jobs
    alter column user_id set default auth.uid();

-- 2. Atomic quota increment. Creates the row with count=1 if absent.
create or replace function public.increment_uploads_today(p_channel_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.channel_quota (channel_id, uploads_today)
    values (p_channel_id, 1)
    on conflict (channel_id) do update
        set uploads_today = public.channel_quota.uploads_today + 1,
            updated_at    = now();
end;
$$;

revoke all on function public.increment_uploads_today(uuid) from public;
grant execute on function public.increment_uploads_today(uuid) to service_role;
