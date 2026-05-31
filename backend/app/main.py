import asyncio
import hashlib
import json
import logging
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.services.ingestion import get_ingestor_for_url
from app.services.cache import video_cache
from app.services.vector_store import vector_store
from app.services.agent import astream_session, stream_chat_message_sse, init_checkpointer, close_checkpointer
from app.worker import analyze_task, celery_app
import uuid
import redis.asyncio as redis_async

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)

# Module-level Redis connection pool — shared across all SSE stream requests.
# Created once at startup, torn down at shutdown.
_redis_pool: Optional[redis_async.ConnectionPool] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage shared resources across the process lifetime."""
    global _redis_pool
    # Open the shared SQLite checkpoint connection once at startup.
    await init_checkpointer()
    # Create the Redis connection pool. Borrowing from a pool avoids creating
    # a new TCP connection for every SSE stream request.
    _redis_pool = redis_async.ConnectionPool.from_url(
        settings.redis_url, decode_responses=True, max_connections=20
    )
    yield
    # Graceful shutdown: close SQLite then drain the Redis pool.
    await close_checkpointer()
    await _redis_pool.aclose()
    logger.info("Redis connection pool closed.")


app = FastAPI(
    title="CreatorJoy Replica API",
    description="Backend API for CreatorJoy's viral script doctor and comparison engine",
    version="0.1.0",
    lifespan=lifespan,
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
    # user_id is supplied by the frontend from the NextAuth session (email or 'anonymous').
    # It is folded into the session hash so two different users analysing the same URL
    # pair each get their own independent LangGraph checkpoint thread.
    user_id: str = "anonymous"


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

    # Deterministic session ID scoped to this user + URL pair.
    # Including user_id prevents two users comparing the same videos from sharing
    # the same LangGraph checkpoint thread (and each other's chat history).
    user_id = req.user_id.strip() or "anonymous"
    session_id = hashlib.md5(f"{user_id}|{url_a}|{url_b}".encode()).hexdigest()

    task_id = str(uuid.uuid4())
    # Fire off Celery background task with a specific task_id so we can
    # revoke it later if the client disconnects.
    analyze_task.apply_async(
        args=[task_id, url_a, url_b, session_id],
        task_id=task_id
    )
    return {"task_id": task_id, "session_id": session_id}

@app.get("/analyze/stream/{task_id}")
async def analyze_stream(task_id: str, request: Request):
    async def _redis_stream_generator():
        # Borrow a connection from the shared pool — no new TCP handshake per request.
        r = redis_async.Redis(connection_pool=_redis_pool)
        completed = False
        try:
            pubsub = r.pubsub()
            channel = f"task_{task_id}"
            events_key = f"task_events_{task_id}"
            await pubsub.subscribe(channel)
            
            # Fetch historical events from Redis list for disconnected clients
            historical_events = await r.lrange(events_key, 0, -1)  # type: ignore
            for event_str in historical_events:
                yield dict(data=event_str)
                try:
                    msg_dict = json.loads(event_str)
                    if msg_dict.get("type") in ("complete", "error"):
                        completed = True
                except json.JSONDecodeError:
                    pass

            if completed:
                await pubsub.unsubscribe(channel)
                return

            try:
                while True:
                    # Check if client disconnected
                    if await request.is_disconnected():
                        logger.info(f"Client disconnected from task {task_id}")
                        break

                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if message and message["type"] == "message":
                        data = message["data"]
                        yield dict(data=data)
                        try:
                            msg_dict = json.loads(str(data))
                            if msg_dict.get("type") in ("complete", "error"):
                                completed = True
                                break
                        except json.JSONDecodeError:
                            pass
                    await asyncio.sleep(0.1)
            finally:
                await pubsub.unsubscribe(channel)
        finally:
            # Release connection back to the pool (does not close the underlying socket).
            await r.aclose()
            
            # If the loop exited early (e.g. client disconnect), cancel the Celery task
            if not completed:
                logger.info(f"Revoking Celery task {task_id} due to stream disconnect")
                celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")

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
