"""Hatchet workflow definitions.

The Hatchet worker process imports this package and registers every workflow
declared inside it. See `workflows.video_pipeline` for the main pipeline.
"""
from __future__ import annotations

from workflows.video_pipeline import process_video_batch

__all__ = ["process_video_batch"]
