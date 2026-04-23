"""Hatchet worker entrypoint.

Usage:
    python -m workflows.worker

Registers both `process_video` and `process_video_batch` with the Hatchet
control plane and blocks forever. Deployed as a long-running Railway
service (see `Procfile` + `railway.json`); one replica is sufficient.
"""
from __future__ import annotations

import structlog

from workflows.hatchet import hatchet
from workflows.video_pipeline import process_video, process_video_batch

_log = structlog.get_logger(__name__)


def main() -> None:
    _log.info("hatchet.worker.start")
    worker = hatchet.worker(
        "kidroo-worker",
        slots=16,
        workflows=[process_video, process_video_batch],
    )
    worker.start()


if __name__ == "__main__":
    main()
