"""Scheduling math for the Hatchet batch workflow."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest


@pytest.fixture
def _import_spread(monkeypatch: pytest.MonkeyPatch):
    # Avoid importing the Hatchet SDK at collection time.
    import importlib
    import sys

    for mod in list(sys.modules):
        if mod.startswith("workflows."):
            sys.modules.pop(mod, None)

    pkg = importlib.import_module("workflows.video_pipeline")
    return pkg._spread_schedule, pkg.ProcessVideoBatchInput


def test_spread_schedule_one_per_day(_import_spread) -> None:
    spread, BatchIn = _import_spread
    start = datetime(2030, 1, 1, tzinfo=timezone.utc)
    batch = BatchIn(
        job_id="j",
        channel_id="c",
        channel_entity_id="e",
        schedule_per_day=1,
        schedule_start=start,
        videos=[
            {
                "video_id": f"v{i}",
                "source_url": "https://",
                "source_video_id": f"s{i}",
                "video_title": f"t{i}",
                "video_description": "",
                "duration_secs": 60,
            }
            for i in range(3)
        ],
    )
    plan = spread(batch)
    assert [p.publish_at.isoformat() for p in plan.items] == [
        "2030-01-01T00:00:00+00:00",
        "2030-01-02T00:00:00+00:00",
        "2030-01-03T00:00:00+00:00",
    ]


def test_spread_schedule_two_per_day(_import_spread) -> None:
    spread, BatchIn = _import_spread
    start = datetime(2030, 1, 1, tzinfo=timezone.utc)
    batch = BatchIn(
        job_id="j",
        channel_id="c",
        channel_entity_id="e",
        schedule_per_day=2,
        schedule_start=start,
        videos=[
            {
                "video_id": f"v{i}",
                "source_url": "https://",
                "source_video_id": f"s{i}",
                "video_title": f"t{i}",
                "video_description": "",
                "duration_secs": 60,
            }
            for i in range(4)
        ],
    )
    plan = spread(batch)
    assert [p.publish_at.isoformat() for p in plan.items] == [
        "2030-01-01T00:00:00+00:00",
        "2030-01-01T12:00:00+00:00",
        "2030-01-02T00:00:00+00:00",
        "2030-01-02T12:00:00+00:00",
    ]
