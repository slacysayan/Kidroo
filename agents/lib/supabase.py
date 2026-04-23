"""Thin Supabase client factory — service-role, cached.

All agent-side DB writes go through the service-role client. RLS is bypassed;
ownership is enforced upstream in the FastAPI layer and the workflow runner.
"""
from __future__ import annotations

from functools import lru_cache

from agents.lib.config import get_settings
from supabase import Client, create_client


@lru_cache(maxsize=1)
def get_service_client() -> Client:
    """Return a cached service-role Supabase client (RLS bypassed)."""
    settings = get_settings()
    return create_client(
        settings.supabase_url,
        settings.supabase_server_key.get_secret_value(),
    )
