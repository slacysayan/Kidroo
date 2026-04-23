-- ─────────────────────────────────────────────────────────────────────────
-- Kidroo — initial schema
-- Migration: 001_initial_schema.sql
--
-- Tables:
--   public.channels       — connected YouTube channels (per user, via Composio)
--   public.jobs           — one row per user submission
--   public.videos         — one row per selected video in a job
--   public.agent_logs     — append-only log stream (Realtime enabled)
--   public.firecrawl_cache — URL-keyed 7-day cache for research scrapes
--
-- RLS: every table is filtered by auth.uid() = user_id where applicable.
-- Realtime: enabled on agent_logs, videos, jobs (for live status updates).
-- ─────────────────────────────────────────────────────────────────────────

-- Extensions ---------------------------------------------------------------

create extension if not exists "pgcrypto";

-- ─── channels ────────────────────────────────────────────────────────────

create table if not exists public.channels (
    id                  uuid        primary key default gen_random_uuid(),
    user_id             uuid        not null references auth.users(id) on delete cascade,
    name                text        not null,                       -- "Finance Daily"
    composio_entity_id  text        not null,                       -- "finance_daily"
    yt_channel_id       text,                                       -- populated after first successful upload
    connected           boolean     not null default false,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now(),
    unique (user_id, composio_entity_id)
);

create index if not exists channels_user_idx on public.channels(user_id);

-- ─── jobs ────────────────────────────────────────────────────────────────

create table if not exists public.jobs (
    id          uuid        primary key default gen_random_uuid(),
    user_id     uuid        not null references auth.users(id) on delete cascade,
    source_url  text        not null,
    status      text        not null default 'pending'
                check (status in ('pending','scanning','awaiting_selection','running','complete','failed','cancelled')),
    channel_id  uuid        references public.channels(id),         -- resolved post-selection
    schedule    jsonb,                                              -- {per_day, start_date, timezone}
    trace_id    uuid        not null default gen_random_uuid(),
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

create index if not exists jobs_user_idx   on public.jobs(user_id);
create index if not exists jobs_status_idx on public.jobs(status);

-- ─── videos ──────────────────────────────────────────────────────────────

create table if not exists public.videos (
    id               uuid        primary key default gen_random_uuid(),
    job_id           uuid        not null references public.jobs(id) on delete cascade,
    source_url       text        not null,
    source_video_id  text,                                          -- YouTube ID on the source side
    title            text,
    description      text,
    tags             text[],
    hashtags         text[],
    category_id      int,
    duration_secs    int,
    status           text        not null default 'queued'
                     check (status in ('queued','fetching','downloading','generating','uploading','scheduled','failed')),
    yt_video_id      text,                                          -- returned by YouTube after upload
    publish_at       timestamptz,
    error_message    text,
    idempotency_key  text,                                          -- sha256(source_video_id + channel_entity_id)
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now()
);

create index if not exists videos_job_idx       on public.videos(job_id);
create index if not exists videos_status_idx    on public.videos(status);
create unique index if not exists videos_idem_uniq
    on public.videos(idempotency_key)
    where idempotency_key is not null;

-- ─── agent_logs (append-only, realtime) ──────────────────────────────────

create table if not exists public.agent_logs (
    id         bigserial   primary key,
    job_id     uuid        not null references public.jobs(id) on delete cascade,
    video_id   uuid        references public.videos(id) on delete cascade,
    agent      text        not null
               check (agent in ('orchestrator','research','metadata','download','upload')),
    step       text        not null
               check (step in ('status','tool_call','reasoning','fallback','error')),
    message    text        not null,
    metadata   jsonb       not null default '{}'::jsonb,            -- {tool, latency_ms, retry, cache_hit, ...}
    trace_id   uuid,
    span_id    uuid        not null default gen_random_uuid(),
    created_at timestamptz not null default now()
);

create index if not exists agent_logs_job_idx     on public.agent_logs(job_id, created_at);
create index if not exists agent_logs_video_idx   on public.agent_logs(video_id, created_at);

-- ─── firecrawl_cache (research-agent cache) ──────────────────────────────

create table if not exists public.firecrawl_cache (
    url_sha256 text        primary key,                             -- sha256 hex of the source URL
    url        text        not null,
    markdown   text        not null,
    metadata   jsonb,
    created_at timestamptz not null default now(),
    expires_at timestamptz not null default (now() + interval '7 days')
);

create index if not exists firecrawl_cache_expires_idx on public.firecrawl_cache(expires_at);

-- ─── channel_quota (YouTube upload quota tracker; Phase 5) ───────────────

create table if not exists public.channel_quota (
    channel_id       uuid        primary key references public.channels(id) on delete cascade,
    uploads_today    int         not null default 0,
    daily_limit      int         not null default 6,
    reset_at         timestamptz not null default (date_trunc('day', now()) + interval '1 day'),
    updated_at       timestamptz not null default now()
);

-- ─── failed_jobs (Phase 5 dead-letter view) ──────────────────────────────

create or replace view public.failed_jobs as
select j.*,
       (select count(*) from public.videos v where v.job_id = j.id and v.status = 'failed') as failed_count
from public.jobs j
where j.status = 'failed';

-- ─── updated_at trigger ──────────────────────────────────────────────────

create or replace function public.set_updated_at() returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

drop trigger if exists set_updated_at on public.channels;
create trigger set_updated_at before update on public.channels
    for each row execute function public.set_updated_at();

drop trigger if exists set_updated_at on public.jobs;
create trigger set_updated_at before update on public.jobs
    for each row execute function public.set_updated_at();

drop trigger if exists set_updated_at on public.videos;
create trigger set_updated_at before update on public.videos
    for each row execute function public.set_updated_at();

-- ─── Row-level security ──────────────────────────────────────────────────

alter table public.channels     enable row level security;
alter table public.jobs         enable row level security;
alter table public.videos       enable row level security;
alter table public.agent_logs   enable row level security;
alter table public.firecrawl_cache enable row level security;
alter table public.channel_quota   enable row level security;

-- channels: owner-only
create policy channels_owner on public.channels
    for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- jobs: owner-only
create policy jobs_owner on public.jobs
    for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- videos: via job ownership
create policy videos_owner on public.videos
    for all using (
        exists (select 1 from public.jobs j where j.id = videos.job_id and j.user_id = auth.uid())
    );

-- agent_logs: read-only to owning user (service role writes)
create policy agent_logs_owner_select on public.agent_logs
    for select using (
        exists (select 1 from public.jobs j where j.id = agent_logs.job_id and j.user_id = auth.uid())
    );

-- firecrawl_cache, channel_quota: service-role only (no user policies — RLS blocks anon)
-- (Service role bypasses RLS by default — leaving no policies here is intentional.)

-- ─── Realtime publication ────────────────────────────────────────────────

-- Enable Realtime on agent_logs (agent step stream) + videos + jobs (status flips).
alter publication supabase_realtime add table public.agent_logs;
alter publication supabase_realtime add table public.videos;
alter publication supabase_realtime add table public.jobs;
