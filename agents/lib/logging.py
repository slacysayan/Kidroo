import os
import structlog
from typing import Any, Dict, Optional
from supabase import create_client, AsyncClient

# Configure structlog
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger()

_supabase: Optional[AsyncClient] = None

async def get_supabase() -> AsyncClient:
    global _supabase
    if _supabase is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        # create_client returns AsyncClient if we use the async version.
        # It is a synchronous factory function, so it must NOT be awaited.
        _supabase = create_client(url, key, is_async=True)
    return _supabase

async def log_step(
    job_id: str,
    agent: str,
    step: str,
    message: str,
    video_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    trace_id: Optional[str] = None,
) -> None:
    """Log an agent step to Supabase and local logger."""
    log_data = {
        "job_id": job_id,
        "video_id": video_id,
        "agent": agent,
        "step": step,
        "message": message,
        "metadata": metadata or {},
        "trace_id": trace_id,
    }

    logger.info("agent_step", **log_data)

    try:
        supabase = await get_supabase()
        await supabase.table("agent_logs").insert(log_data).execute()
    except Exception as e:
        logger.error("failed_to_log_to_supabase", error=str(e))
