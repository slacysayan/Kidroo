"""Structured logger that writes to both stdout (structlog) and Supabase `agent_logs`.

Schema invariants (see supabase/migrations/001_initial_schema.sql):
    agent_logs.agent    ∈ {orchestrator, research, metadata, download, upload}
    agent_logs.step     ∈ {status, tool_call, reasoning, fallback, error}
    agent_logs.message  text
    agent_logs.metadata jsonb  (level, partial, provider, tool, latency_ms, ...)
    agent_logs.trace_id / span_id  correlation

Usage:
    async with JobLogger(job_id=..., video_id=..., agent="research") as log:
        await log.status("Scanning source URL", tool="yt-dlp")
        await log.tool_call("firecrawl.scrape_url", latency_ms=420)
        await log.reasoning_delta("partial tokens...", provider="groq")
        await log.error("Quota exhausted", exception="RateLimitError")
"""
from __future__ import annotations

import asyncio
import contextlib
import contextvars
import uuid
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any, Literal, Self, TypeAlias

import structlog

from agents.lib.config import get_settings
from supabase import Client, create_client

Step = Literal["status", "tool_call", "reasoning", "fallback", "error"]
Level = Literal["debug", "info", "warning", "error"]

# JSON-serialisable values we accept as structured log metadata. Typed as a
# constrained alias (instead of plain `Any`) so the public logging surface
# stays documentable and callers get a meaningful signature.
LogMetaValue: TypeAlias = (
    str | int | float | bool | None | list[Any] | dict[str, Any]
)

_trace_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "trace_id", default=None
)

_log = structlog.get_logger(__name__)


class JobLoggerFlushError(RuntimeError):
    """Raised when agent_logs insertion exhausts retries and drops rows."""

    def __init__(self, *, dropped: int, cause: Exception | None) -> None:
        msg = f"agent_logs: {dropped} rows dropped after retries"
        if cause is not None:
            msg = f"{msg} (last error: {cause!r})"
        super().__init__(msg)
        self.dropped = dropped
        self.cause = cause


def _new_id() -> str:
    return str(uuid.uuid4())


def _supabase_server() -> Client:
    """Service-role Supabase client. Bypasses RLS — server-only."""
    settings = get_settings()
    return create_client(
        settings.supabase_url,
        settings.supabase_server_key.get_secret_value(),
    )


@dataclass
class JobLogger:
    """Async context manager that batches `agent_logs` inserts.

    One logger instance per agent-run. `trace_id` is shared across all
    emissions from the same agent-run; a fresh `span_id` is issued per row.
    """

    job_id: str
    video_id: str | None
    agent: str
    trace_id: str = field(default_factory=_new_id)
    _supa: Client | None = field(default=None, init=False)
    _queue: asyncio.Queue[dict[str, Any]] = field(
        default_factory=asyncio.Queue, init=False
    )
    _flush_task: asyncio.Task[None] | None = field(default=None, init=False)
    _dropped_rows: int = field(default=0, init=False)
    _last_flush_error: Exception | None = field(default=None, init=False)

    async def __aenter__(self) -> Self:
        self._supa = _supabase_server()
        _trace_id_ctx.set(self.trace_id)
        self._flush_task = asyncio.create_task(self._flush_loop())
        await self.status("agent started", lifecycle="start")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc is not None:
            await self.error(
                str(exc),
                exception=exc_type.__name__ if exc_type else None,
                lifecycle="abort",
            )
        else:
            await self.status("agent finished", lifecycle="end")
        # drain the queue then stop the flusher
        await self._queue.join()
        if self._flush_task:
            self._flush_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._flush_task

        # If the flusher permanently dropped any rows, surface that as a
        # JobLoggerFlushError so the caller (workflow / agent) sees an
        # explicit terminal failure instead of silent log loss. We only
        # raise when the wrapped scope itself didn't already raise — the
        # original exception always takes precedence.
        if exc is None and self._dropped_rows:
            raise JobLoggerFlushError(
                dropped=self._dropped_rows,
                cause=self._last_flush_error,
            )

    # ─── public API ────────────────────────────────────────────────────────

    async def status(self, message: str, **meta: LogMetaValue) -> None:
        """Log a status update (agent lifecycle, phase, progress)."""
        await self._emit("status", "info", message, **meta)

    async def tool_call(
        self,
        tool: str,
        *,
        latency_ms: int | None = None,
        **meta: LogMetaValue,
    ) -> None:
        """Log a structured tool invocation with optional latency."""
        await self._emit(
            "tool_call", "info", tool, tool=tool, latency_ms=latency_ms, **meta
        )

    async def reasoning_delta(
        self,
        text: str,
        *,
        provider: str,
        partial: bool = True,
        **meta: LogMetaValue,
    ) -> None:
        """Record a streamed LLM reasoning chunk (partial tokens)."""
        await self._emit(
            "reasoning",
            "info",
            text,
            provider=provider,
            partial=partial,
            **meta,
        )

    async def fallback(
        self,
        reason: str,
        *,
        provider_from: str,
        provider_to: str,
        **meta: LogMetaValue,
    ) -> None:
        """Log a provider/key failover event (e.g. Groq → Cerebras)."""
        await self._emit(
            "fallback",
            "warning",
            reason,
            provider_from=provider_from,
            provider_to=provider_to,
            **meta,
        )

    async def warning(self, message: str, **meta: LogMetaValue) -> None:
        """Log a warning. Stored as a `status` row per the schema."""
        await self._emit("status", "warning", message, **meta)

    async def info(self, message: str, **meta: LogMetaValue) -> None:
        """Alias of :meth:`status` for call-site readability."""
        await self.status(message, **meta)

    async def error(self, message: str, **meta: LogMetaValue) -> None:
        """Log an error event. Records a terminal `error` row."""
        await self._emit("error", "error", message, **meta)

    # ─── impl ──────────────────────────────────────────────────────────────

    async def _emit(
        self,
        step: Step,
        level: Level,
        message: str,
        **meta: LogMetaValue,
    ) -> None:
        row: dict[str, Any] = {
            "job_id": self.job_id,
            "video_id": self.video_id,
            "agent": self.agent,
            "step": step,
            "message": message[:2000],  # bandwidth cap per schema note
            "metadata": {
                "level": level,
                **{k: v for k, v in meta.items() if v is not None},
            },
            "trace_id": self.trace_id,
            "span_id": _new_id(),
        }
        _log.info(
            "agent.emit",
            agent=self.agent,
            step=step,
            level=level,
            job_id=self.job_id,
            video_id=self.video_id,
            message=message,
        )
        await self._queue.put(row)

    async def _flush_loop(self) -> None:
        """Batch-insert rows into `agent_logs`.

        Each batch is retried with exponential backoff (3 attempts) before it
        is marked as a drop. If the *final* drop happens, the row count is
        recorded on the logger so ``__aexit__`` can surface a terminal
        failure instead of silently swallowing the loss.
        """
        assert self._supa is not None
        supa = self._supa
        while True:
            rows: list[dict[str, Any]] = [await self._queue.get()]
            try:
                while not self._queue.empty() and len(rows) < 64:
                    rows.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                pass

            delivered = False
            last_error: Exception | None = None
            for attempt in range(3):
                try:
                    await asyncio.to_thread(
                        lambda batch=rows: supa.table("agent_logs")
                        .insert(batch)
                        .execute()
                    )
                    delivered = True
                    break
                except Exception as e:
                    last_error = e
                    _log.warning(
                        "agent_logs.insert_retrying",
                        error=str(e),
                        attempt=attempt + 1,
                        n=len(rows),
                    )
                    await asyncio.sleep(0.25 * (2**attempt))

            if not delivered:
                self._dropped_rows += len(rows)
                self._last_flush_error = last_error
                _log.error(
                    "agent_logs.insert_dropped",
                    error=str(last_error),
                    n=len(rows),
                    dropped_total=self._dropped_rows,
                )

            for _ in rows:
                self._queue.task_done()
