import asyncio
import hashlib
import json
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.services.ingestion import get_ingestor_for_url
from app.services.cache import video_cache
from app.services.vector_store import vector_store
from app.services.agent import astream_session, stream_chat_message_sse
from app.worker import analyze_task
import uuid
import redis.asyncio as redis_async

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)

app = FastAPI(
    title="CreatorJoy Replica API",
    description="Backend API for CreatorJoy's viral script doctor and comparison engine",
    version="0.1.0"
)

# Configure rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore

# CORS — origins configurable via CORS_ORIGINS env var.
# Credentials require explicit method/header lists (not wildcard).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "Authorization"],
)


class AnalyzeRequest(BaseModel):
    url_a: str
    url_b: str
    # session_id is derived server-side from the URL pair (MD5 hash) to ensure
    # deterministic reuse and prevent client-supplied collisions.


class ChatRequest(BaseModel):
    session_id: str
    message: str


@app.get("/health")
@limiter.limit("60/minute")
async def health_check(request: Request):
    return {
        "status": "healthy",
        "google_configured": bool(settings.google_api_key),
        "openai_configured": bool(settings.openai_api_key),
    }


@app.post("/analyze")
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def analyze_videos(request: Request, req: AnalyzeRequest):
    url_a = req.url_a.strip()
    url_b = req.url_b.strip()

    if not url_a or not url_b:
        raise HTTPException(status_code=400, detail="Both video URLs are required.")

    # Deterministic session ID based on the URL pair — shared for cache hits.
    session_id = hashlib.md5(f"{url_a}|{url_b}".encode()).hexdigest()

    task_id = str(uuid.uuid4())
    # Fire off Celery background task
    analyze_task.delay(task_id, url_a, url_b, session_id)
    return {"task_id": task_id, "session_id": session_id}

@app.get("/analyze/stream/{task_id}")
async def analyze_stream(task_id: str):
    async def _redis_stream_generator():
        r = redis_async.Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            pubsub = r.pubsub()
            channel = f"task_{task_id}"
            await pubsub.subscribe(channel)
            try:
                while True:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if message and message["type"] == "message":
                        data = message["data"]
                        yield dict(data=data)
                        try:
                            msg_dict = json.loads(str(data))
                            if msg_dict.get("type") in ("complete", "error"):
                                break
                        except json.JSONDecodeError:
                            pass
                    await asyncio.sleep(0.1)
            finally:
                await pubsub.unsubscribe(channel)
        finally:
            await r.aclose()
            
    return EventSourceResponse(_redis_stream_generator())


@app.post("/chat/stream")
@limiter.limit(f"{settings.rate_limit_per_minute * 2}/minute")
async def chat_stream(request: Request, req: ChatRequest):
    if not req.session_id or not req.message:
        raise HTTPException(status_code=400, detail="session_id and message are required.")

    generator = stream_chat_message_sse(req.session_id, req.message)
    return EventSourceResponse(generator)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
