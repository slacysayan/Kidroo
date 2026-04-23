"""FastAPI entrypoint.

Stateless REST API — realtime fanout happens via Supabase Realtime, not here.

Endpoints (Phase 1):
  GET  /health                       — liveness
  GET  /auth/me                      — echo the authenticated user (Supabase JWT)
  POST /jobs                         — enqueue a new job on Hatchet
  GET  /jobs/{job_id}                — job status (server-side Supabase read)

Phase 2 adds /agents/* introspection endpoints.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agents.lib.config import get_settings

_log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    settings = get_settings()
    _log.info(
        "api.startup",
        pipeline_enabled=settings.pipeline_enabled,
        max_concurrent=settings.max_concurrent_videos_per_user,
    )
    yield
    _log.info("api.shutdown")


app = FastAPI(
    title="Kidroo API",
    description="Agentic YouTube content pipeline — stateless REST surface.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in Phase 5 to the deployed frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── dependencies ────────────────────────────────────────────────────────

async def current_user(request: Request) -> dict[str, Any]:
    """Extract + verify the Supabase JWT from the Authorization header.

    Phase 1 stub: accepts `Authorization: Bearer <supabase jwt>` but does not
    yet verify the signature. Phase 5 wires up real verification against the
    Supabase JWKS endpoint.
    """
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    token = auth.split(" ", 1)[1]
    # TODO(phase-5): verify against SUPABASE_URL + /auth/v1/.well-known/jwks.json
    return {"token": token}


# ─── routes ──────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str = "ok"
    pipeline_enabled: bool


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(pipeline_enabled=get_settings().pipeline_enabled)


@app.get("/auth/me")
async def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return {"authenticated": True, **user}


class CreateJobRequest(BaseModel):
    source_url: str = Field(description="YouTube channel, playlist, or video URL")
    target_channels: list[str] = Field(
        description="Composio entity IDs the output should be published to",
        min_length=1,
    )
    selected_video_ids: list[str] | None = Field(
        default=None,
        description="Subset of source videos; None = ask the user",
    )


class CreateJobResponse(BaseModel):
    job_id: str
    status: str = "enqueued"


@app.post("/jobs", response_model=CreateJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    req: CreateJobRequest,
    user: dict[str, Any] = Depends(current_user),
) -> CreateJobResponse:
    """Enqueue a new video-pipeline job on Hatchet. (Full wiring in Phase 3.)"""
    if not get_settings().pipeline_enabled:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "pipeline kill-switch is engaged"
        )
    # TODO(phase-3): await hatchet.admin.run_workflow("process_video_batch", req)
    raise HTTPException(
        status.HTTP_501_NOT_IMPLEMENTED,
        "job dispatch lands in Phase 3 (docs/ROADMAP.md)",
    )
