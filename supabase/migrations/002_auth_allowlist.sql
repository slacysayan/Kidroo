-- ─────────────────────────────────────────────────────────────────────────
-- Kidroo — email allowlist + pre-signup hook
-- Migration: 002_auth_allowlist.sql
--
-- Purpose:
--   Restrict Supabase Auth signups to a static allowlist of emails. Public
--   signups (email+password OR magic link OR Google OAuth) all pass through
--   this guard because Supabase calls the `check_email_allowlist` function
--   from the `before_signup` Auth Hook.
--
-- Setup (one-time, manual):
--   1. Run this migration.
--   2. In Supabase Dashboard → Authentication → Hooks → "Before user created",
--      select the `check_email_allowlist` function.
-- ─────────────────────────────────────────────────────────────────────────

create table if not exists public.allowed_emails (
    email       text        primary key,
    added_by    uuid        references auth.users(id) on delete set null,
    created_at  timestamptz not null default now()
);

-- Seed (edit here to add/remove allowed users — or maintain via Studio UI):
-- Uncomment + set real addresses before applying.
-- insert into public.allowed_emails(email) values
--   ('sayan@example.com'),
--   ('founder@example.com')
-- on conflict (email) do nothing;

alter table public.allowed_emails enable row level security;

-- Service-role only — no user policies.
revoke all on public.allowed_emails from public, anon, authenticated;

-- ─── Before-signup hook ──────────────────────────────────────────────────
-- Supabase Auth Hooks: https://supabase.com/docs/guides/auth/auth-hooks
-- The function receives an `event` JSONB:
--   { "user": { "email": "...", "id": "...", ... }, ... }
-- and returns either `{}` (allow) or `{"error": {"message": "...", "http_code": 403}}`.

create or replace function public.check_email_allowlist(event jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    user_email text;
begin
    user_email := lower(coalesce(event->'user'->>'email', ''));
    if user_email = '' then
        return jsonb_build_object(
            'error',
            jsonb_build_object(
                'http_code', 400,
                'message', 'email is required'
            )
        );
    end if;

    if exists (select 1 from public.allowed_emails where lower(email) = user_email) then
        return '{}'::jsonb;
    end if;

    return jsonb_build_object(
        'error',
        jsonb_build_object(
            'http_code', 403,
            'message', 'this email is not on the Kidroo access list'
        )
    );
end;
$$;

grant execute on function public.check_email_allowlist(jsonb) to supabase_auth_admin;
revoke execute on function public.check_email_allowlist(jsonb) from public, anon, authenticated;
