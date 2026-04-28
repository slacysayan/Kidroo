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

from pydantic import SecretStr, model_validator
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
    # Optional at config-parse time so `./scripts/dev.sh` can boot the API
    # and web without provisioning Hatchet first. Code that actually starts
    # or dispatches workflow runs must call `require_hatchet_client_token()`
    # to fail fast when the token is missing.
    hatchet_client_token: SecretStr | None = None
    hatchet_client_host_port: str = "engine.hatchet-tools.com:7077"

    # ─── App ───────────────────────────────────────────────────────────────
    # Default OFF: the upload agent only calls Composio's YOUTUBE_UPLOAD_VIDEO
    # when this is True. Local dev should leave this False so the rest of the
    # DAG can run end-to-end without publishing real videos.
    pipeline_enabled: bool = False
    max_concurrent_videos_per_user: int = 6
    download_staging_dir: Path = Path("/tmp/kidroo")
    log_level: str = "info"

    # Comma-separated list of origins allowed to make credentialed
    # cross-origin requests to the API. Leave unset during local dev to get
    # the ``http://localhost:3000`` default; in production set this to the
    # Vercel deploy URL (and any custom domain).
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse ``cors_origins`` into a deduped list of non-empty origins."""
        seen: list[str] = []
        for raw in self.cors_origins.split(","):
            origin = raw.strip()
            if origin and origin not in seen:
                seen.append(origin)
        return seen

    def require_hatchet_client_token(self) -> SecretStr:
        """Return the Hatchet client token or raise if it is missing.

        Call this from code paths that actually need Hatchet (worker startup,
        `hatchet.runs.create(...)`). Importing `agents.lib.config` for any
        other reason must not require the token.
        """
        if self.hatchet_client_token is None:
            raise ValueError(
                "HATCHET_CLIENT_TOKEN is not set. Set it in `.env` (or the "
                "Railway service env) before running the worker or starting "
                "a workflow."
            )
        return self.hatchet_client_token

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
