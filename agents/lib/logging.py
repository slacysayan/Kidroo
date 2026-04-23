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
import contextvars
import uuid
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any, Literal, Self

import structlog
from supabase import Client, create_client

from agents.lib.config import get_settings

Step = Literal["status", "tool_call", "reasoning", "fallback", "error"]
Level = Literal["debug", "info", "warning", "error"]

_trace_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "trace_id", default=None
)

_log = structlog.get_logger(__name__)


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
            try:
                await self._flush_task
            except (asyncio.CancelledError, Exception):
                pass

    # ─── public API ────────────────────────────────────────────────────────

    async def status(self, message: str, **meta: Any) -> None:
        await self._emit("status", "info", message, **meta)

    async def tool_call(
        self, tool: str, *, latency_ms: int | None = None, **meta: Any
    ) -> None:
        await self._emit(
            "tool_call", "info", tool, tool=tool, latency_ms=latency_ms, **meta
        )

    async def reasoning_delta(
        self,
        text: str,
        *,
        provider: str,
        partial: bool = True,
        **meta: Any,
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
        **meta: Any,
    ) -> None:
        await self._emit(
            "fallback",
            "warning",
            reason,
            provider_from=provider_from,
            provider_to=provider_to,
            **meta,
        )

    async def warning(self, message: str, **meta: Any) -> None:
        # warnings that aren't fallback events are still `status` per schema
        await self._emit("status", "warning", message, **meta)

    async def info(self, message: str, **meta: Any) -> None:  # convenience alias
        await self.status(message, **meta)

    async def error(self, message: str, **meta: Any) -> None:
        await self._emit("error", "error", message, **meta)

    # ─── impl ──────────────────────────────────────────────────────────────

    async def _emit(
        self,
        step: Step,
        level: Level,
        message: str,
        **meta: Any,
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
        """Batch-insert rows into `agent_logs` in the background."""
        assert self._supa is not None
        supa = self._supa
        while True:
            rows: list[dict[str, Any]] = [await self._queue.get()]
            try:
                while not self._queue.empty() and len(rows) < 64:
                    rows.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                pass
            try:
                await asyncio.to_thread(
                    lambda batch=rows: supa.table("agent_logs").insert(batch).execute()
                )
            except Exception as e:
                _log.error("agent_logs.insert failed", error=str(e), n=len(rows))
            finally:
                for _ in rows:
                    self._queue.task_done()
