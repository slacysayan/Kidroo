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


class _HatchetProxy:
    """Lazy import-safe facade around :func:`get_hatchet`.

    ``from workflows.hatchet import hatchet`` must not crash if Hatchet
    credentials aren't fully wired yet (e.g. during docs generation, tests
    that never touch the workflow, or ``/health`` probes before env is set).
    The client is built on first attribute access.
    """

    __slots__ = ()

    def __getattr__(self, name: str) -> object:
        return getattr(get_hatchet(), name)


hatchet = _HatchetProxy()
