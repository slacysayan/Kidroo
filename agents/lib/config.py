"""Typed configuration.

All environment variables are declared here. Missing required keys fail at
startup with a clear Pydantic validation error — no "KeyError at 3am".

Usage:
    from agents.lib.config import get_settings
    settings = get_settings()
    settings.groq_api_key
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration.

    Values are pulled from (in order of precedence):
      1. Real environment variables
      2. `.env` at repo root (if present)

    Secrets use `SecretStr` so they never leak into logs or repr() output.
    """

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ─── LLMs ──────────────────────────────────────────────────────────────
    groq_api_key: SecretStr
    groq_model: str = "llama-3.3-70b-versatile"
    cerebras_api_key: SecretStr
    cerebras_model: str = "llama-3.3-70b"

    # ─── Research tools ────────────────────────────────────────────────────
    tavily_api_key: SecretStr
    tavily_api_key_fallback: SecretStr | None = None
    firecrawl_api_key: SecretStr
    exa_api_key: SecretStr

    # ─── Integrations ──────────────────────────────────────────────────────
    composio_api_key: SecretStr

    # ─── Supabase ──────────────────────────────────────────────────────────
    supabase_url: str
    supabase_anon_key: SecretStr | None = None
    supabase_publishable_key: SecretStr | None = None
    supabase_service_key: SecretStr | None = None
    supabase_secret_key: SecretStr | None = None
    supabase_db_url: SecretStr

    # ─── Hatchet ───────────────────────────────────────────────────────────
    hatchet_client_token: SecretStr
    hatchet_client_host_port: str = "engine.hatchet-tools.com:7077"

    # ─── App ───────────────────────────────────────────────────────────────
    pipeline_enabled: bool = True
    max_concurrent_videos_per_user: int = 6
    download_staging_dir: Path = Path("/tmp/kidroo")
    log_level: str = "info"

    @property
    def supabase_client_key(self) -> SecretStr:
        """Prefer the new publishable key; fall back to the legacy anon JWT."""
        if self.supabase_publishable_key:
            return self.supabase_publishable_key
        if self.supabase_anon_key:
            return self.supabase_anon_key
        raise ValueError(
            "Either SUPABASE_PUBLISHABLE_KEY or SUPABASE_ANON_KEY must be set."
        )

    @property
    def supabase_server_key(self) -> SecretStr:
        """Prefer the new secret key; fall back to the legacy service-role JWT."""
        if self.supabase_secret_key:
            return self.supabase_secret_key
        if self.supabase_service_key:
            return self.supabase_service_key
        raise ValueError(
            "Either SUPABASE_SECRET_KEY or SUPABASE_SERVICE_KEY must be set."
        )

    @model_validator(mode="after")
    def _validate_supabase_keys(self) -> Settings:
        """Ensure at least one client-side and one server-side Supabase key exists."""
        if not (self.supabase_publishable_key or self.supabase_anon_key):
            raise ValueError(
                "Supabase client key missing: set SUPABASE_PUBLISHABLE_KEY "
                "(preferred) or SUPABASE_ANON_KEY."
            )
        if not (self.supabase_secret_key or self.supabase_service_key):
            raise ValueError(
                "Supabase server key missing: set SUPABASE_SECRET_KEY "
                "(preferred) or SUPABASE_SERVICE_KEY."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a singleton `Settings` instance. Cached for the process lifetime."""
    return Settings()  # type: ignore[call-arg]
