"""Structured logger that writes to both stdout (structlog) and Supabase `agent_logs`.

Every log entry carries `trace_id`, `span_id`, `job_id`, `video_id`, and `agent`
so we get free OpenTelemetry-style correlation without importing OTel.

Usage:
    async with JobLogger(job_id=..., video_id=..., agent="research") as log:
        await log.info("Scraping %s", url, step="tool_call", tool="firecrawl")
        await log.reasoning_delta("partial tokens here...", provider="groq")
"""
from __future__ import annotations

import asyncio
import contextvars
import uuid
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any, Self

import structlog
from supabase import Client, create_client

from agents.lib.config import get_settings

_trace_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "trace_id", default=None
)

_log = structlog.get_logger(__name__)


def _new_id() -> str:
    return uuid.uuid4().hex


def _supabase_server() -> Client:
    """Service-role Supabase client. Bypasses RLS — server-only."""
    settings = get_settings()
    return create_client(
        settings.supabase_url,
        settings.supabase_server_key.get_secret_value(),
    )


@dataclass
class JobLogger:
    """Async context manager that batches `agent_logs` inserts."""

    job_id: str
    video_id: str | None
    agent: str
    trace_id: str = field(default_factory=_new_id)
    _supa: Client | None = field(default=None, init=False)
    _queue: asyncio.Queue[dict[str, Any]] = field(
        default_factory=asyncio.Queue, init=False
    )
    _flush_task: asyncio.Task[None] | None = field(default=None, init=False)

    async def __aenter__(self) -> Self:
        self._supa = _supabase_server()
        _trace_id_ctx.set(self.trace_id)
        self._flush_task = asyncio.create_task(self._flush_loop())
        await self.info("agent started", step="lifecycle")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc is not None:
            await self.error(str(exc), step="lifecycle", exception=exc_type.__name__ if exc_type else None)
        else:
            await self.info("agent finished", step="lifecycle")
        # drain
        await self._queue.join()
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except (asyncio.CancelledError, Exception):
                pass

    # ─── public API ────────────────────────────────────────────────────────

    async def info(self, message: str, **kw: Any) -> None:
        await self._emit("info", message, **kw)

    async def warning(self, message: str, **kw: Any) -> None:
        await self._emit("warning", message, **kw)

    async def error(self, message: str, **kw: Any) -> None:
        await self._emit("error", message, **kw)

    async def reasoning_delta(
        self,
        text: str,
        *,
        provider: str,
        partial: bool = True,
        **kw: Any,
    ) -> None:
        """Record a streamed LLM reasoning chunk (partial tokens)."""
        await self._emit(
            "info",
            text,
            step="reasoning",
            partial=partial,
            provider=provider,
            **kw,
        )

    # ─── impl ──────────────────────────────────────────────────────────────

    async def _emit(self, level: str, message: str, **kw: Any) -> None:
        span_id = _new_id()
        row: dict[str, Any] = {
            "job_id": self.job_id,
            "video_id": self.video_id,
            "agent": self.agent,
            "trace_id": self.trace_id,
            "span_id": span_id,
            "level": level,
            "message": message,
            "meta": {k: v for k, v in kw.items() if v is not None},
        }
        # stdout (structured)
        _log.log(
            getattr(_log, level, _log.info).__name__ if False else level,
            message,
            **{k: v for k, v in row.items() if k not in {"message"}},
        )
        await self._queue.put(row)

    async def _flush_loop(self) -> None:
        """Batch-insert rows into `agent_logs` in the background."""
        assert self._supa is not None
        while True:
            rows: list[dict[str, Any]] = [await self._queue.get()]
            # opportunistically drain the queue for a micro-batch
            try:
                while not self._queue.empty() and len(rows) < 64:
                    rows.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                pass
            try:
                # supabase-py is sync — run in executor to stay non-blocking
                await asyncio.to_thread(
                    lambda: self._supa.table("agent_logs").insert(rows).execute()  # type: ignore[union-attr]
                )
            except Exception as e:
                _log.error("agent_logs.insert failed", error=str(e), n=len(rows))
            finally:
                for _ in rows:
                    self._queue.task_done()
