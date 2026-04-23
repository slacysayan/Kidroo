import os
import logging
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Kidroo API")

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to your Vercel URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REQUIRED_ENV_VARS = [
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "GROQ_API_KEY",
    "CEREBRAS_API_KEY",
    "COMPOSIO_API_KEY",
    "FIRECRAWL_API_KEY",
    "EXA_API_KEY",
]

@app.on_event("startup")
async def startup_event():
    missing = [var for var in REQUIRED_ENV_VARS if not os.environ.get(var)]
    if missing:
        logger.warning(f"Missing required environment variables: {', '.join(missing)}")
        # In a real production environment, you might want to exit here
        # but for now we'll just log a warning.

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

class JobCreate(BaseModel):
    source_url: str

@app.post("/jobs")
async def create_job(job: JobCreate):
    # This will be implemented in Phase 2
    return {"job_id": "placeholder", "status": "pending"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
