from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.services.ingestion import get_ingestor_for_url
from app.services.cache import video_cache
from app.services.vector_store import vector_store
from app.services.agent import initialize_session, stream_chat_message_sse
from app.services.channel_analytics import generate_mock_channel_analytics

app = FastAPI(
    title="CreatorJoy Replica API",
    description="Backend API for CreatorJoy's viral script doctor and comparison engine",
    version="0.1.0"
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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
    session_id = req.session_id

    if not url_a or not url_b:
        raise HTTPException(status_code=400, detail="Both video URLs are required.")

    # 1. Fetch Video A (Check cache first)
    data_a = video_cache.get(url_a)
    if not data_a:
        try:
            ingestor_a = get_ingestor_for_url(url_a)
            data_a = ingestor_a.ingest(url_a)
            video_cache.set(url_a, data_a)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to ingest Video A: {str(e)}")

    # 2. Fetch Video B (Check cache first)
    data_b = video_cache.get(url_b)
    if not data_b:
        try:
            ingestor_b = get_ingestor_for_url(url_b)
            data_b = ingestor_b.ingest(url_b)
            video_cache.set(url_b, data_b)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to ingest Video B: {str(e)}")

    # 3. Index transcripts in Vector DB
    try:
        vector_store.index_transcript(data_a["video_id"], data_a["transcript"])
        vector_store.index_transcript(data_b["video_id"], data_b["transcript"])
    except Exception as e:
        # Log error and continue to keep app operational
        app_logger = settings.google_api_key # Dummy to avoid logger complaints
        print(f"Vector indexing error: {e}")

    # 4. Initialize LangGraph Session & Hook Audit
    try:
        session_result = initialize_session(session_id, data_a, data_b)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize LangGraph agent session: {str(e)}")

    return {
        "video_a": {
            "video_id": data_a["video_id"],
            "platform": data_a["platform"],
            "title": data_a["title"],
            "metrics": data_a["metrics"],
            "engagement_rate": data_a["engagement_rate"],
            "whisper_stubbed": data_a.get("whisper_stubbed", False),
            "is_estimated_views": data_a.get("is_estimated_views", False),
        },
        "video_b": {
            "video_id": data_b["video_id"],
            "platform": data_b["platform"],
            "title": data_b["title"],
            "metrics": data_b["metrics"],
            "engagement_rate": data_b["engagement_rate"],
            "whisper_stubbed": data_b.get("whisper_stubbed", False),
            "is_estimated_views": data_b.get("is_estimated_views", False),
        },
        "hook_analysis": session_result["hook_analysis"],
        "is_mock_analysis": session_result.get("is_mock_analysis", False),
        "chat_history": session_result["messages"]
    }

@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    if not req.session_id or not req.message:
        raise HTTPException(status_code=400, detail="session_id and message are required.")
    
    # Return streaming SSE Response
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
