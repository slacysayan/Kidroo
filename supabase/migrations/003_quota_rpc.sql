-- ─────────────────────────────────────────────────────────────────────────
-- Kidroo — atomic quota increment RPC
-- Migration: 003_quota_rpc.sql
--
-- Purpose:
--   Provide an atomic way to increment `uploads_today` in `channel_quota`.
--   Prevents race conditions in the read-modify-write pattern.
-- ─────────────────────────────────────────────────────────────────────────

create or replace function public.increment_channel_quota(target_channel_id uuid)
returns void
language plpgsql
security definer
as $$
begin
    insert into public.channel_quota (channel_id, uploads_today)
    values (target_channel_id, 1)
    on conflict (channel_id)
    do update set
        uploads_today = public.channel_quota.uploads_today + 1,
        updated_at = now();
end;
$$;

grant execute on function public.increment_channel_quota(uuid) to authenticated, service_role;
