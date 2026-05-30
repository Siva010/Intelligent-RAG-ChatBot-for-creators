import asyncio
import json
import logging
from typing import Dict, Any
import redis.asyncio as redis_async
from celery import Celery

from app.config import settings
from app.services.ingestion import get_ingestor_for_url
from app.services.cache import video_cache
from app.services.vector_store import vector_store
from app.services.agent import astream_session

logger = logging.getLogger(__name__)

celery_broker_url = settings.redis_url
if celery_broker_url.startswith("rediss://") and "ssl_cert_reqs" not in celery_broker_url:
    delimiter = "&" if "?" in celery_broker_url else "?"
    celery_broker_url += f"{delimiter}ssl_cert_reqs=CERT_NONE"

celery_app = Celery(
    "creatorjoy",
    broker=celery_broker_url,
    backend=celery_broker_url
)

async def _async_analyze_task(task_id: str, url_a: str, url_b: str, session_id: str):
    r = redis_async.Redis.from_url(settings.redis_url, decode_responses=True)
    channel = f"task_{task_id}"

    async def _publish(msg_dict: dict):
        await r.publish(channel, json.dumps(msg_dict))

    async def _ingest(url: str, label: str):
        await _publish({"type": "progress", "message": f"Downloading {label}..."})
        cached = video_cache.get(url)
        if cached:
            await _publish({"type": "progress", "message": f"{label} loaded from cache."})
            return cached
        try:
            ingestor = get_ingestor_for_url(url)
            data = await asyncio.to_thread(ingestor.ingest, url)
            video_cache.set(url, data)
            await _publish({"type": "progress", "message": f"{label} downloaded successfully."})
            return data
        except Exception as e:
            await _publish({"type": "error", "message": f"Failed to ingest {label}: {str(e)}"})
            raise

    async def _index(data: dict, label: str):
        await _publish({"type": "progress", "message": f"Indexing {label} into vector store..."})
        await asyncio.to_thread(vector_store.index_transcript, data["video_id"], data["transcript"])
        await _publish({"type": "progress", "message": f"{label} indexed successfully."})

    try:
        data_a, data_b = await asyncio.gather(
            _ingest(url_a, "Video A"),
            _ingest(url_b, "Video B"),
        )

        try:
            await asyncio.gather(
                _index(data_a, "Video A"),
                _index(data_b, "Video B"),
            )
        except Exception as e:
            logger.warning(f"Vector indexing error: {e}")
            await _publish({"type": "progress", "message": f"Warning: Vector indexing error: {e}"})

        await _publish({"type": "progress", "message": "Assembling RAG Context & Generating Hook Audit..."})
        
        session_meta: Dict[str, Any] = {}
        async for evt_type, payload in astream_session(session_id, data_a, data_b):
            if evt_type == "hook_chunk":
                await _publish({"type": "hook_chunk", "chunk": payload})
            elif evt_type == "done" and isinstance(payload, dict):
                session_meta = payload

        await _publish({"type": "complete", "data": {
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
            "is_mock_analysis": session_meta.get("is_mock_analysis", False),
            "chat_history": session_meta.get("chat_history", []),
            "session_id": session_id,
        }})
    except Exception as e:
        logger.error(f"Worker error: {e}")
        await _publish({"type": "error", "message": f"Worker encountered an error: {str(e)}"})
    finally:
        await r.aclose()

@celery_app.task(name="analyze_task")
def analyze_task(task_id: str, url_a: str, url_b: str, session_id: str):
    asyncio.run(_async_analyze_task(task_id, url_a, url_b, session_id))
    return {"status": "completed"}
