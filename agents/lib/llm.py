"""Streaming LLM wrapper — Groq primary, Cerebras fallback.

The canonical entrypoint for any agent that needs an LLM. Every token is
streamed; partial chunks are flushed to `agent_logs` every 32 tokens or
400 ms so the UI sees the model think in real time.

Failover contract:
  - **Pre-stream failure** (429 / 5xx / timeout before any token): switch to
    Cerebras transparently, caller is unaware.
  - **Mid-stream failure** (connection drops after N tokens): log fallback,
    re-issue to Cerebras with already-generated tokens prepended as an
    assistant turn so the model **continues** rather than restarts.
  - **Both providers fail**: raise `LLMUnavailableError` (non-retryable —
    Hatchet `NonRetryableError` in the caller).
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any, Literal

import structlog
from cerebras.cloud.sdk import AsyncCerebras
from groq import AsyncGroq

from agents.lib.config import get_settings
from agents.lib.logging import JobLogger

_log = structlog.get_logger(__name__)

# Flush cadence for partial tokens.
_FLUSH_TOKENS = 32
_FLUSH_MS = 400

Provider = Literal["groq", "cerebras"]


class LLMUnavailableError(RuntimeError):
    """Both Groq and Cerebras failed — caller should NOT retry."""


async def _groq_stream(
    *,
    system: str,
    user: str,
    response_format: str | None,
    model: str | None,
    extra: dict[str, Any],
) -> AsyncIterator[str]:
    settings = get_settings()
    client = AsyncGroq(api_key=settings.groq_api_key.get_secret_value())
    req: dict[str, Any] = {
        "model": model or settings.groq_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": True,
    }
    if response_format == "json":
        req["response_format"] = {"type": "json_object"}
    req.update(extra)

    stream = await client.chat.completions.create(**req)
    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta


async def _cerebras_stream(
    *,
    system: str,
    user: str,
    assistant_prefix: str | None,
    response_format: str | None,
    model: str | None,
    extra: dict[str, Any],
) -> AsyncIterator[str]:
    settings = get_settings()
    client = AsyncCerebras(api_key=settings.cerebras_api_key.get_secret_value())
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    if assistant_prefix:
        # Continue the partial completion rather than restart.
        messages.append({"role": "assistant", "content": assistant_prefix})

    req: dict[str, Any] = {
        "model": model or settings.cerebras_model,
        "messages": messages,
        "stream": True,
    }
    if response_format == "json":
        req["response_format"] = {"type": "json_object"}
    req.update(extra)

    stream = await client.chat.completions.create(**req)
    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta


async def stream_complete(
    *,
    system: str,
    user: str,
    logger: JobLogger,
    response_format: str | None = None,
    model: str | None = None,
    **extra: Any,
) -> AsyncIterator[str]:
    """Stream tokens from Groq (primary) → Cerebras (fallback).

    The caller receives the same async iterator regardless of provider.
    Partial tokens are flushed to `agent_logs` on the side for the UI.

    Args:
        system: System prompt.
        user: User message.
        logger: `JobLogger` carrying job_id/video_id/agent.
        response_format: `"json"` forces JSON-mode on both providers.
        model: Override the default model for this call.
        extra: Forwarded to both provider SDKs.

    Yields:
        Content deltas as they arrive.

    Raises:
        LLMUnavailableError: Both providers failed. Non-retryable.
    """
    generated = ""
    token_count = 0
    last_flush_ts = time.monotonic()
    buffered = ""
    provider: Provider = "groq"
    start = time.monotonic()
    fallback_occurred = False

    async def _flush(force: bool = False) -> None:
        nonlocal buffered, last_flush_ts
        if not buffered:
            return
        now = time.monotonic()
        should = (
            force
            or token_count % _FLUSH_TOKENS == 0
            or (now - last_flush_ts) * 1000 >= _FLUSH_MS
        )
        if should:
            await logger.reasoning_delta(
                buffered, provider=provider, partial=True
            )
            buffered = ""
            last_flush_ts = now

    # ── Attempt 1: Groq ──────────────────────────────────────────────────
    try:
        async for delta in _groq_stream(
            system=system,
            user=user,
            response_format=response_format,
            model=model,
            extra=extra,
        ):
            generated += delta
            buffered += delta
            token_count += 1
            yield delta
            await _flush()
    except Exception as groq_err:
        is_prestream = not generated
        await logger.fallback(
            f"Groq stream failed ({type(groq_err).__name__}); failing over to Cerebras",
            provider_from="groq",
            provider_to="cerebras",
            prestream=is_prestream,
            tokens_so_far=token_count,
            error=str(groq_err),
        )
        fallback_occurred = True
        provider = "cerebras"

        # ── Attempt 2: Cerebras (continues from already-generated text) ─
        try:
            async for delta in _cerebras_stream(
                system=system,
                user=user,
                assistant_prefix=generated or None,
                response_format=response_format,
                model=model,
                extra=extra,
            ):
                generated += delta
                buffered += delta
                token_count += 1
                yield delta
                await _flush()
        except Exception as cerebras_err:
            await logger.error(
                "Both Groq and Cerebras failed",
                groq_error=str(groq_err),
                cerebras_error=str(cerebras_err),
            )
            raise LLMUnavailableError(
                f"Groq: {groq_err!r} | Cerebras: {cerebras_err!r}"
            ) from cerebras_err

    # final flush
    await _flush(force=True)
    latency_ms = int((time.monotonic() - start) * 1000)
    await logger.status(
        "LLM stream complete",
        provider=provider,
        tokens=token_count,
        latency_ms=latency_ms,
        fallback_occurred=fallback_occurred,
    )
