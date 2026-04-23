"""Hatchet client singleton.

Any caller (API, worker, CLI) imports `hatchet` from here rather than
re-instantiating. Auth uses `HATCHET_CLIENT_TOKEN` resolved from `Settings`.
"""
from __future__ import annotations

import os
from functools import lru_cache

from hatchet_sdk import Hatchet

from agents.lib.config import get_settings


@lru_cache(maxsize=1)
def get_hatchet() -> Hatchet:
    """Return a process-wide Hatchet client.

    The SDK reads `HATCHET_CLIENT_TOKEN` + `HATCHET_CLIENT_HOST_PORT` from the
    environment. We ensure both are set from our typed `Settings` so a single
    source of truth applies across API / workflow / worker processes.
    """
    settings = get_settings()
    os.environ.setdefault(
        "HATCHET_CLIENT_TOKEN", settings.hatchet_client_token.get_secret_value()
    )
    os.environ.setdefault(
        "HATCHET_CLIENT_HOST_PORT", settings.hatchet_client_host_port
    )
    return Hatchet(debug=settings.log_level.lower() == "debug")


hatchet = get_hatchet()
