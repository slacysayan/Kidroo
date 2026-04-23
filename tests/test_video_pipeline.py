"""Scheduling math for the Hatchet batch workflow."""
from __future__ import annotations

from datetime import UTC, datetime

from workflows.pipeline_models import ProcessVideoBatchInput, _spread_schedule


def _make_batch(per_day: int, count: int) -> ProcessVideoBatchInput:
    return ProcessVideoBatchInput(
        job_id="j",
        channel_id="c",
        channel_entity_id="e",
        schedule_per_day=per_day,
        schedule_start=datetime(2030, 1, 1, tzinfo=UTC),
        videos=[
            {
                "video_id": f"v{i}",
                "source_url": "https://",
                "source_video_id": f"s{i}",
                "video_title": f"t{i}",
                "video_description": "",
                "duration_secs": 60,
            }
            for i in range(count)
        ],
    )


def test_spread_schedule_one_per_day() -> None:
    plan = _spread_schedule(_make_batch(per_day=1, count=3))
    assert [p.publish_at.isoformat() for p in plan.items] == [
        "2030-01-01T00:00:00+00:00",
        "2030-01-02T00:00:00+00:00",
        "2030-01-03T00:00:00+00:00",
    ]


def test_spread_schedule_two_per_day() -> None:
    plan = _spread_schedule(_make_batch(per_day=2, count=4))
    assert [p.publish_at.isoformat() for p in plan.items] == [
        "2030-01-01T00:00:00+00:00",
        "2030-01-01T12:00:00+00:00",
        "2030-01-02T00:00:00+00:00",
        "2030-01-02T12:00:00+00:00",
    ]
