"""BaseAgent — parent class for every runtime agent.

Gives every subclass:
  - typed `Input` / `Output` Pydantic models (enforced via generics).
  - a `JobLogger` (trace_id / span_id correlation for free).
  - a `stream_complete()` helper pre-bound with job_id / video_id / agent.

Subclass contract (see `.agents/skills/agents-runtime/SKILL.md`):

    class Input(BaseModel): ...
    class Output(BaseModel): ...

    class MyAgent(BaseAgent[Input, Output]):
        name = "my"
        async def run(self, inp: Input) -> Output: ...
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, ClassVar, Generic, TypeVar

from pydantic import BaseModel

from agents.lib.llm import stream_complete as _stream_complete
from agents.lib.logging import JobLogger

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class BaseAgent(ABC, Generic[InputT, OutputT]):
    name: ClassVar[str] = "base"

    def __init__(self, *, job_id: str, video_id: str | None = None) -> None:
        self.job_id = job_id
        self.video_id = video_id
        self._logger: JobLogger | None = None

    @property
    def log(self) -> JobLogger:
        if self._logger is None:
            raise RuntimeError(
                "JobLogger not initialised — use `async with agent.bound():` "
                "or call `await agent.start()` first."
            )
        return self._logger

    async def __aenter__(self) -> BaseAgent[InputT, OutputT]:
        self._logger = JobLogger(
            job_id=self.job_id, video_id=self.video_id, agent=self.name
        )
        await self._logger.__aenter__()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._logger is not None:
            await self._logger.__aexit__(exc_type, exc, tb)
            self._logger = None

    # ─── helpers for subclasses ───────────────────────────────────────────

    def stream(
        self,
        *,
        system: str,
        user: str,
        response_format: str | None = None,
        model: str | None = None,
        **extra: Any,
    ) -> AsyncIterator[str]:
        """Stream an LLM completion with this agent's logger pre-bound."""
        return _stream_complete(
            system=system,
            user=user,
            logger=self.log,
            response_format=response_format,
            model=model,
            **extra,
        )

    @abstractmethod
    async def run(self, inp: InputT) -> OutputT:
        """Execute the agent's main task. Implemented by subclasses."""
        raise NotImplementedError
