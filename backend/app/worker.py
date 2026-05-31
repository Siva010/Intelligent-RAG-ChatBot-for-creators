import json
import logging
from typing import Dict, Any
import redis
from concurrent.futures import ThreadPoolExecutor
from celery import Celery

from app.config import settings
from app.services.ingestion import get_ingestor_for_url
from app.services.cache import video_cache
from app.services.vector_store import vector_store
from app.services.agent import stream_session_sync, init_sync_checkpointer, close_sync_checkpointer

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

@celery_app.task(name="analyze_task")
def analyze_task(task_id: str, url_a: str, url_b: str, session_id: str):
    pool = redis.ConnectionPool.from_url(settings.redis_url, decode_responses=True)
    r = redis.Redis(connection_pool=pool)
    channel = f"task_{task_id}"
    events_key = f"task_events_{task_id}"

    init_sync_checkpointer()

    def _publish(msg_dict: dict):
        msg_str = json.dumps(msg_dict)
        r.rpush(events_key, msg_str)
        r.expire(events_key, 3600)
        r.publish(channel, msg_str)

    def _ingest(url: str, label: str):
        _publish({"type": "progress", "message": f"Downloading {label}..."})
        cached = video_cache.get(url)
        if cached:
            _publish({"type": "progress", "message": f"{label} loaded from cache."})
            return cached
        try:
            ingestor = get_ingestor_for_url(url)
            data = ingestor.ingest(url)
            video_cache.set(url, data)
            _publish({"type": "progress", "message": f"{label} downloaded successfully."})
            return data
        except Exception as e:
            _publish({"type": "error", "message": f"Failed to ingest {label}: {str(e)}"})
            raise

    def _index(data: dict, label: str):
        _publish({"type": "progress", "message": f"Indexing {label} into vector store..."})
        vector_store.index_transcript(data["video_id"], data["transcript"])
        _publish({"type": "progress", "message": f"{label} indexed successfully."})

    try:
        with ThreadPoolExecutor(max_workers=2) as ex:
            fut_a = ex.submit(_ingest, url_a, "Video A")
            fut_b = ex.submit(_ingest, url_b, "Video B")
            data_a = fut_a.result()
            data_b = fut_b.result()

        try:
            with ThreadPoolExecutor(max_workers=2) as ex:
                ex.submit(_index, data_a, "Video A")
                ex.submit(_index, data_b, "Video B")
        except Exception as e:
            logger.warning(f"Vector indexing error: {e}")
            _publish({"type": "progress", "message": f"Warning: Vector indexing error: {e}"})

        _publish({"type": "progress", "message": "Assembling RAG Context & Generating Hook Audit..."})
        
        session_meta: Dict[str, Any] = {}
        for evt_type, payload in stream_session_sync(session_id, data_a, data_b):
            if evt_type == "hook_chunk":
                _publish({"type": "hook_chunk", "chunk": payload})
            elif evt_type == "done" and isinstance(payload, dict):
                session_meta = payload

        _publish({"type": "complete", "data": {
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
        _publish({"type": "error", "message": f"Worker encountered an error: {str(e)}"})
    finally:
        close_sync_checkpointer() # close SQLite connection
        r.close()   # return connection to pool
        pool.disconnect()  # drain and close the task-scoped pool
    
    return {"status": "completed"}
