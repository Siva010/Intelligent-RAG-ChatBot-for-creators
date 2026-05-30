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

    async def _analyze_generator():
        q: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()

        async def _ingest(url: str, label: str):
            """Fetch one video — checks Redis cache first, then runs yt-dlp in a thread."""
            await q.put({"type": "progress", "message": f"Downloading {label}..."})
            cached = video_cache.get(url)
            if cached:
                await q.put({"type": "progress", "message": f"{label} loaded from cache."})
                return cached
            try:
                ingestor = get_ingestor_for_url(url)
                data = await asyncio.to_thread(ingestor.ingest, url)
                video_cache.set(url, data)
                await q.put({"type": "progress", "message": f"{label} downloaded successfully."})
                return data
            except Exception as e:
                await q.put({"type": "error", "message": f"Failed to ingest {label}: {str(e)}"})
                raise

        async def _index(data: dict, label: str):
            await q.put({"type": "progress", "message": f"Indexing {label} into vector store..."})
            await asyncio.to_thread(vector_store.index_transcript, data["video_id"], data["transcript"])
            await q.put({"type": "progress", "message": f"{label} indexed successfully."})

        async def _run_analysis():
            try:
                # 1 + 2. Fetch both videos in parallel
                data_a, data_b = await asyncio.gather(
                    _ingest(url_a, "Video A"),
                    _ingest(url_b, "Video B"),
                )

                # 3. Index both transcripts in parallel
                try:
                    await asyncio.gather(
                        _index(data_a, "Video A"),
                        _index(data_b, "Video B"),
                    )
                except Exception as e:
                    logger.warning(f"Vector indexing error: {e}")
                    await q.put({"type": "progress", "message": f"Warning: Vector indexing error: {e}"})

                # 4. Initialise LangGraph session & stream the hook audit
                await q.put({"type": "progress", "message": "Assembling RAG Context & Generating Hook Audit..."})
                session_meta: Dict[str, Any] = {}
                async for evt_type, payload in astream_session(session_id, data_a, data_b):
                    if evt_type == "hook_chunk":
                        await q.put({"type": "hook_chunk", "chunk": payload})
                    elif evt_type == "done" and isinstance(payload, dict):
                        session_meta = payload

                await q.put({"type": "complete", "data": {
                    "video_a": {
                        "video_id": data_a["video_id"],
                        "platform": data_a["platform"],
                        "title": data_a["title"],
                        "creator": data_a.get("creator", "Unknown"),
                        "follower_count": data_a.get("follower_count", 0),
                        "hashtags": data_a.get("hashtags", []),
                        "upload_date": data_a.get("upload_date", "Unknown"),
                        "thumbnail_url": data_a.get("thumbnail_url", ""),
                        "metrics": data_a["metrics"],
                        "engagement_rate": data_a["engagement_rate"],
                        "whisper_stubbed": data_a.get("whisper_stubbed", False),
                        "asr_method": data_a.get("asr_method", "none"),
                        "is_estimated_views": data_a.get("is_estimated_views", False),
                        "transcript": data_a.get("transcript", []),
                    },
                    "video_b": {
                        "video_id": data_b["video_id"],
                        "platform": data_b["platform"],
                        "title": data_b["title"],
                        "creator": data_b.get("creator", "Unknown"),
                        "follower_count": data_b.get("follower_count", 0),
                        "hashtags": data_b.get("hashtags", []),
                        "upload_date": data_b.get("upload_date", "Unknown"),
                        "thumbnail_url": data_b.get("thumbnail_url", ""),
                        "metrics": data_b["metrics"],
                        "engagement_rate": data_b["engagement_rate"],
                        "whisper_stubbed": data_b.get("whisper_stubbed", False),
                        "asr_method": data_b.get("asr_method", "none"),
                        "is_estimated_views": data_b.get("is_estimated_views", False),
                        "transcript": data_b.get("transcript", []),
                    },
                    "hook_analysis": session_meta.get("hook_analysis", ""),
                    "is_mock_analysis": session_meta.get("is_mock_analysis", False),
                    "chat_history": session_meta.get("chat_history", []),
                    "session_id": session_id,
                }})
            except Exception as e:
                await q.put({"type": "error", "message": str(e)})

        task = asyncio.create_task(_run_analysis())

        while True:
            msg = await q.get()
            yield dict(data=json.dumps(msg))
            if msg["type"] in ("complete", "error"):
                break

        await task

    return EventSourceResponse(_analyze_generator())


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
