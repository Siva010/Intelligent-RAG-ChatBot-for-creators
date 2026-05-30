import asyncio
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.services.ingestion import get_ingestor_for_url
from app.services.cache import video_cache
from app.services.vector_store import vector_store
from app.services.agent import astream_session, stream_chat_message_sse
from app.services.channel_analytics import generate_mock_channel_analytics

app = FastAPI(
    title="CreatorJoy Replica API",
    description="Backend API for CreatorJoy's viral script doctor and comparison engine",
    version="0.1.0"
)

# Enable CORS — origins are loaded from settings (configurable via CORS_ORIGINS env var)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    url_a: str
    url_b: str
    session_id: str

class ChatRequest(BaseModel):
    session_id: str
    message: str

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "google_configured": bool(settings.google_api_key),
        "openai_configured": bool(settings.openai_api_key)
    }

@app.post("/analyze")
async def analyze_videos(req: AnalyzeRequest):
    url_a = req.url_a
    url_b = req.url_b
    import hashlib
    session_id = hashlib.md5(f"{url_a}|{url_b}".encode()).hexdigest()

    if not url_a or not url_b:
        raise HTTPException(status_code=400, detail="Both video URLs are required.")

    async def _analyze_generator():
        q: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()

        async def _ingest(url: str, label: str):
            """Fetch one video — checks cache first, then runs yt-dlp in a thread."""
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
                raise e

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
                    import logging
                    logging.getLogger(__name__).warning(f"Vector indexing error: {e}")
                    await q.put({"type": "progress", "message": f"Warning: Vector indexing error: {e}"})

                # 4. Initialize LangGraph Session & Hook Audit (streaming)
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
                    },
                    "hook_analysis": session_meta.get("hook_analysis", ""),
                    "is_mock_analysis": session_meta.get("is_mock_analysis", False),
                    "chat_history": session_meta.get("chat_history", []),
                    "session_id": session_id
                }})
            except Exception as e:
                # If an error wasn't already caught and queued, catch it here
                await q.put({"type": "error", "message": str(e)})

        # Start the background task
        task = asyncio.create_task(_run_analysis())

        while True:
            # Yield items from the queue as they come in
            msg = await q.get()
            import json
            yield dict(data=json.dumps(msg))
            
            if msg["type"] in ["complete", "error"]:
                break
                
        # ensure the task finishes cleanly
        await task

    return EventSourceResponse(_analyze_generator())

@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    if not req.session_id or not req.message:
        raise HTTPException(status_code=400, detail="session_id and message are required.")

    # Return streaming SSE Response
    # stream_chat_message_sse internally offloads blocking LLM work to a thread
    generator = stream_chat_message_sse(req.session_id, req.message)
    return EventSourceResponse(generator)

@app.get("/channel/{channel_id}/analytics")
async def get_channel_analytics(channel_id: str):
    """
    Returns channel-level analytical data (mocked for demo purposes).
    """
    if not channel_id:
        raise HTTPException(status_code=400, detail="channel_id is required.")
    
    return generate_mock_channel_analytics(channel_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
