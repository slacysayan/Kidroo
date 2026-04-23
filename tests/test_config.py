"""Settings validation — failures should be loud and fast."""
from __future__ import annotations

import pytest

from agents.lib.config import Settings, get_settings


def test_settings_loads_from_env() -> None:
    settings = get_settings()
    assert settings.groq_model == "llama-3.3-70b-versatile"
    assert settings.cerebras_model == "llama-3.3-70b"
    assert str(settings.supabase_url) == "https://fake.supabase.co"
    assert settings.supabase_client_key.get_secret_value() == "sb_publishable_fake"
    assert settings.supabase_server_key.get_secret_value() == "sb_secret_fake"


def test_missing_supabase_keys_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPABASE_PUBLISHABLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    get_settings.cache_clear()
    with pytest.raises(Exception):
        Settings()  # type: ignore[call-arg]


def test_pipeline_enabled_default_true() -> None:
    settings = get_settings()
    assert settings.pipeline_enabled is True
