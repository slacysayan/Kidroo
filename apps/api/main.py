"""FastAPI entrypoint.

Stateless REST API — realtime fanout happens via Supabase Realtime, not here.

Endpoints:
  GET  /health                       — liveness + kill-switch state
  GET  /auth/me                      — echo the authenticated user (Supabase JWT)
  POST /jobs                         — create a job row and enqueue on Hatchet
  GET  /jobs/{job_id}                — return the job row + its videos
  POST /jobs/{job_id}/scan           — yt-dlp scan; writes detected videos
  POST /jobs/{job_id}/start          — kick off the Hatchet batch workflow
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agents.download.skills.ytdlp import scan as ytdlp_scan
from agents.lib.config import get_settings
from agents.lib.supabase import get_service_client
from supabase import Client, create_client

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
    version="0.2.0",
    lifespan=lifespan,
)

# Pin CORS to the configured frontend origins. Wildcarding `allow_origins`
# together with `allow_credentials=True` would let any site make credentialed
# cross-origin requests (including Supabase cookie-based sessions) against
# this API, enabling CSRF from arbitrary origins. Set `CORS_ORIGINS` in the
# deployed environment to a comma-separated list of the Vercel / custom domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["authorization", "content-type"],
)


# ─── dependencies ────────────────────────────────────────────────────────


def _anon_client() -> Client:
    settings = get_settings()
    return create_client(
        settings.supabase_url, settings.supabase_client_key.get_secret_value()
    )


async def current_user(request: Request) -> dict[str, Any]:
    """Verify the Supabase access token and return its payload.

    We delegate signature verification to Supabase's own `auth.getUser()`
    endpoint rather than re-implementing JWKS — it's one RPC and saves us from
    key-rotation bugs.
    """
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    token = auth.split(" ", 1)[1]

    def _verify() -> dict[str, Any]:
        client = _anon_client()
        resp = client.auth.get_user(token)
        if resp is None or resp.user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
        return {"id": resp.user.id, "email": resp.user.email, "token": token}

    return await asyncio.to_thread(_verify)


# ─── routes ──────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str = "ok"
    pipeline_enabled: bool
    version: str = "0.2.0"


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(pipeline_enabled=get_settings().pipeline_enabled)


@app.get("/auth/me")
async def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return {"authenticated": True, "id": user["id"], "email": user["email"]}


# ─── jobs ────────────────────────────────────────────────────────────────


class CreateJobRequest(BaseModel):
    source_url: str = Field(description="YouTube channel, playlist, or video URL")


class CreateJobResponse(BaseModel):
    job_id: str
    status: str


@app.post(
    "/jobs",
    response_model=CreateJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_job(
    req: CreateJobRequest,
    user: dict[str, Any] = Depends(current_user),
) -> CreateJobResponse:
    if not get_settings().pipeline_enabled:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "pipeline kill-switch is engaged"
        )

    def _insert() -> dict[str, Any]:
        supa = get_service_client()
        resp = (
            supa.table("jobs")
            .insert(
                {
                    "user_id": user["id"],
                    "source_url": req.source_url,
                    "status": "pending",
                }
            )
            .execute()
        )
        row = (resp.data or [{}])[0]
        return row

    row = await asyncio.to_thread(_insert)
    return CreateJobResponse(job_id=row["id"], status=row["status"])


@app.get("/jobs/{job_id}")
async def get_job(
    job_id: str, user: dict[str, Any] = Depends(current_user)
) -> dict[str, Any]:
    def _q() -> dict[str, Any]:
        supa = get_service_client()
        job = (
            supa.table("jobs")
            .select("*")
            .eq("id", job_id)
            .eq("user_id", user["id"])
            .limit(1)
            .execute()
        )
        if not job.data:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
        videos = (
            supa.table("videos").select("*").eq("job_id", job_id).execute()
        )
        return {"job": job.data[0], "videos": videos.data or []}

    return await asyncio.to_thread(_q)


@app.post("/jobs/{job_id}/scan")
async def scan_job(
    job_id: str, user: dict[str, Any] = Depends(current_user)
) -> dict[str, Any]:
    """Run yt-dlp scan on the job's source_url and persist detected videos."""

    def _load() -> dict[str, Any]:
        supa = get_service_client()
        resp = (
            supa.table("jobs")
            .select("id, source_url, user_id, status")
            .eq("id", job_id)
            .eq("user_id", user["id"])
            .limit(1)
            .execute()
        )
        if not resp.data:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
        return resp.data[0]

    job = await asyncio.to_thread(_load)

    videos = await ytdlp_scan(job["source_url"])

    def _persist() -> None:
        supa = get_service_client()
        rows = [
            {
                "job_id": job_id,
                "source_video_id": v.source_video_id,
                "source_url": v.url or job["source_url"],
                "title": v.title,
                "duration_secs": v.duration_secs,
                "status": "queued",
            }
            for v in videos
        ]
        if rows:
            supa.table("videos").insert(rows).execute()
        supa.table("jobs").update({"status": "awaiting_selection"}).eq(
            "id", job_id
        ).execute()

    await asyncio.to_thread(_persist)
    return {"job_id": job_id, "detected": len(videos)}


class StartJobRequest(BaseModel):
    channel_id: str
    video_ids: list[str] = Field(min_length=1)
    per_day: int = Field(1, ge=1, le=6)
    start_date: datetime


class StartJobResponse(BaseModel):
    job_id: str
    workflow_run_id: str | None = None
    status: str = "running"


@app.post("/jobs/{job_id}/start", response_model=StartJobResponse)
async def start_job(
    job_id: str,
    req: StartJobRequest,
    user: dict[str, Any] = Depends(current_user),
) -> StartJobResponse:
    if not get_settings().pipeline_enabled:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "pipeline kill-switch is engaged"
        )

    def _load() -> tuple[dict[str, Any], list[dict[str, Any]]]:
        supa = get_service_client()
        job = (
            supa.table("jobs")
            .select("*")
            .eq("id", job_id)
            .eq("user_id", user["id"])
            .limit(1)
            .execute()
        )
        if not job.data:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
        channel = (
            supa.table("channels")
            .select("id, composio_entity_id, name")
            .eq("id", req.channel_id)
            .eq("user_id", user["id"])
            .limit(1)
            .execute()
        )
        if not channel.data:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "channel not found")
        vids = (
            supa.table("videos")
            .select("*")
            .in_("id", req.video_ids)
            .eq("job_id", job_id)
            .execute()
        )
        return (
            {"job": job.data[0], "channel": channel.data[0]},
            vids.data or [],
        )

    meta, vids = await asyncio.to_thread(_load)

    # Build the batch input for Hatchet.
    batch = {
        "job_id": job_id,
        "channel_id": meta["channel"]["id"],
        "channel_entity_id": meta["channel"]["composio_entity_id"],
        "schedule_per_day": req.per_day,
        "schedule_start": req.start_date.astimezone(UTC).isoformat(),
        "videos": [
            {
                "video_id": v["id"],
                "source_url": v["source_url"],
                "source_video_id": v["source_video_id"],
                "video_title": v.get("title") or "",
                "video_description": v.get("description") or "",
                "duration_secs": v.get("duration_secs") or 0,
            }
            for v in vids
        ],
    }

    # Enqueue on Hatchet. We lazily import to avoid hard-requiring Hatchet
    # connectivity for `/health` + `/auth/me`.
    from workflows.hatchet import hatchet

    def _enqueue() -> str:
        # Hatchet v1 SDK removed `admin.run_workflow`; the replacement is the
        # synchronous `runs.create(workflow_name, input)` feature client. We
        # still wrap it in `asyncio.to_thread` to keep the event loop free.
        ref = hatchet.runs.create("process_video_batch", batch)
        return str(ref.workflow_run_id)

    try:
        run_id = await asyncio.to_thread(_enqueue)
    except Exception as e:
        # Keep the raw error in structured logs only; surfacing `str(e)` to
        # the client can leak internal hostnames, auth tokens, or stack
        # fragments from the Hatchet SDK.
        _log.error("hatchet.enqueue_failed", error=str(e))
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "workflow enqueue failed — check server logs",
        ) from e

    def _mark() -> None:
        supa = get_service_client()
        supa.table("jobs").update(
            {
                "status": "running",
                "channel_id": meta["channel"]["id"],
                "schedule": {
                    "per_day": req.per_day,
                    "start_date": req.start_date.date().isoformat(),
                    "timezone": "UTC",
                },
            }
        ).eq("id", job_id).execute()

    await asyncio.to_thread(_mark)

    return StartJobResponse(job_id=job_id, workflow_run_id=run_id, status="running")
