"""Hatchet workflow definitions.

Pure-Python helpers (models + scheduling) live in `workflows.pipeline_models`
and do not depend on the Hatchet SDK — they're unit-testable on their own.

The Hatchet-registered workflows live in `workflows.video_pipeline` and are
wired by `workflows.worker` at runtime.
"""
from __future__ import annotations

__all__ = ["hatchet"]
