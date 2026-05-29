"""
FastAPI integration tests for app/main.py

Uses FastAPI's built-in TestClient (synchronous) and httpx.AsyncClient
for the async SSE endpoints. All service calls are mocked so no real
network requests, no LLM calls, and no running server is required.

Run with: pytest tests/test_api.py -v
"""
import sys
import os
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

VIDEO_A_PAYLOAD = {
    "video_id": "vid_a",
    "platform": "youtube",
    "title": "Test Video A",
    "creator": "Creator A",
    "follower_count": 500_000,
    "hashtags": ["#test"],
    "upload_date": "2024-01-15",
    "thumbnail_url": "https://img.youtube.com/vi/vid_a/maxresdefault.jpg",
    "metrics": {"views": 1_000_000, "likes": 40_000, "comments": 1_000, "duration": 600},
    "engagement_rate": 4.1,
    "is_estimated_views": False,
    "whisper_stubbed": False,
    "asr_method": "youtube_captions",
    "transcript": [{"text": "Hook text here", "start": 0.0, "duration": 3.0}],
}

VIDEO_B_PAYLOAD = {
    "video_id": "vid_b",
    "platform": "youtube",
    "title": "Test Video B",
    "creator": "Creator B",
    "follower_count": 100_000,
    "hashtags": ["#test"],
    "upload_date": "2024-02-01",
    "thumbnail_url": "https://img.youtube.com/vi/vid_b/maxresdefault.jpg",
    "metrics": {"views": 500_000, "likes": 30_000, "comments": 800, "duration": 480},
    "engagement_rate": 6.16,
    "is_estimated_views": False,
    "whisper_stubbed": False,
    "asr_method": "youtube_captions",
    "transcript": [{"text": "Competitor hook", "start": 0.0, "duration": 3.0}],
}


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_response_has_status_key(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_response_has_api_key_flags(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert "google_configured" in data
        assert "openai_configured" in data
        assert isinstance(data["google_configured"], bool)
        assert isinstance(data["openai_configured"], bool)


# ---------------------------------------------------------------------------
# POST /analyze — validation
# ---------------------------------------------------------------------------

class TestAnalyzeValidation:
    def test_missing_body_returns_422(self, client):
        resp = client.post("/analyze")
        assert resp.status_code == 422

    def test_missing_url_b_returns_422(self, client):
        resp = client.post("/analyze", json={"url_a": "https://yt.com/a", "session_id": "s1"})
        assert resp.status_code == 422

    def test_empty_url_a_returns_400(self, client):
        resp = client.post("/analyze", json={
            "url_a": "",
            "url_b": "https://yt.com/b",
            "session_id": "s1",
        })
        # Our route checks for empty strings and raises 400
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /analyze — SSE streaming flow (mocked ingestor + agent)
# ---------------------------------------------------------------------------

def _make_sse_complete_event():
    """Build the 'complete' SSE payload the mocked astream_session yields."""
    return {
        "type": "complete",
        "data": {
            "video_a": VIDEO_A_PAYLOAD,
            "video_b": VIDEO_B_PAYLOAD,
            "hook_analysis": "Video B wins the hook phase.",
            "is_mock_analysis": True,
            "chat_history": [],
        },
    }


async def _fake_astream_session(session_id, data_a, data_b):
    """Async generator that mimics astream_session without touching LangGraph."""
    yield ("hook_chunk", "### Hook Audit\n\n")
    yield ("hook_chunk", "Video B wins with higher engagement.")
    yield ("done", {
        "hook_analysis": "Video B wins with higher engagement.",
        "is_mock_analysis": True,
        "chat_history": [],
    })


class TestAnalyzeSSEFlow:
    def _run_sse(self, client, url_a, url_b, session_id="test_session"):
        """Helper: POST /analyze and collect all SSE messages into a list."""
        with patch("app.main.get_ingestor_for_url") as mock_ingestor_factory, \
             patch("app.main.vector_store") as mock_vs, \
             patch("app.main.astream_session", side_effect=_fake_astream_session):

            mock_ingestor = MagicMock()
            mock_ingestor.ingest.side_effect = [
                dict(VIDEO_A_PAYLOAD),
                dict(VIDEO_B_PAYLOAD),
            ]
            mock_ingestor_factory.return_value = mock_ingestor
            mock_vs.index_transcript.return_value = None

            with client.stream("POST", "/analyze", json={
                "url_a": url_a,
                "url_b": url_b,
                "session_id": session_id,
            }) as response:
                assert response.status_code == 200
                messages = []
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str and data_str != "[DONE]":
                            messages.append(json.loads(data_str))
                return messages

    def test_sse_contains_progress_messages(self, client):
        messages = self._run_sse(
            client,
            "https://www.youtube.com/watch?v=aaa",
            "https://www.youtube.com/watch?v=bbb",
        )
        types = [m["type"] for m in messages]
        assert "progress" in types

    def test_sse_contains_hook_chunk_messages(self, client):
        messages = self._run_sse(
            client,
            "https://www.youtube.com/watch?v=aaa",
            "https://www.youtube.com/watch?v=bbb",
        )
        types = [m["type"] for m in messages]
        assert "hook_chunk" in types

    def test_sse_ends_with_complete_message(self, client):
        messages = self._run_sse(
            client,
            "https://www.youtube.com/watch?v=aaa",
            "https://www.youtube.com/watch?v=bbb",
        )
        types = [m["type"] for m in messages]
        assert "complete" in types

    def test_complete_message_has_video_data(self, client):
        messages = self._run_sse(
            client,
            "https://www.youtube.com/watch?v=aaa",
            "https://www.youtube.com/watch?v=bbb",
        )
        complete = next(m for m in messages if m["type"] == "complete")
        assert "video_a" in complete["data"]
        assert "video_b" in complete["data"]
        assert "hook_analysis" in complete["data"]

    def test_complete_message_has_asr_method(self, client):
        messages = self._run_sse(
            client,
            "https://www.youtube.com/watch?v=aaa",
            "https://www.youtube.com/watch?v=bbb",
        )
        complete = next(m for m in messages if m["type"] == "complete")
        assert "asr_method" in complete["data"]["video_a"]
        assert "asr_method" in complete["data"]["video_b"]


# ---------------------------------------------------------------------------
# POST /chat/stream — validation + SSE
# ---------------------------------------------------------------------------

class TestChatStreamValidation:
    def test_missing_body_returns_422(self, client):
        resp = client.post("/chat/stream")
        assert resp.status_code == 422

    def test_missing_message_returns_422(self, client):
        resp = client.post("/chat/stream", json={"session_id": "s1"})
        assert resp.status_code == 422

    def test_missing_session_id_returns_422(self, client):
        resp = client.post("/chat/stream", json={"message": "hello"})
        assert resp.status_code == 422


class TestChatStreamSSE:
    def test_unknown_session_yields_error_chunk_and_done(self, client):
        with client.stream("POST", "/chat/stream", json={
            "session_id": "totally_unknown_session_xyz",
            "message": "tell me something",
        }) as response:
            assert response.status_code == 200
            lines = list(response.iter_lines())

        data_lines = [l[6:] for l in lines if l.startswith("data: ")]
        # Must contain an error chunk
        error_chunks = [json.loads(d) for d in data_lines if d != "[DONE]" and "Error" in d]
        assert len(error_chunks) > 0
        # Must end with [DONE]
        assert "[DONE]" in data_lines

    def test_always_ends_with_done_sentinel(self, client):
        with client.stream("POST", "/chat/stream", json={
            "session_id": "no_such_session_abc",
            "message": "hello",
        }) as response:
            lines = list(response.iter_lines())

        data_values = [l[6:] for l in lines if l.startswith("data: ")]
        assert "[DONE]" in data_values


# ---------------------------------------------------------------------------
# GET /channel/{channel_id}/analytics  (mock data endpoint)
# ---------------------------------------------------------------------------

class TestChannelAnalyticsEndpoint:
    def test_returns_200_for_valid_channel(self, client):
        resp = client.get("/channel/UCtest123/analytics")
        assert resp.status_code == 200

    def test_response_is_json(self, client):
        resp = client.get("/channel/UCtest123/analytics")
        data = resp.json()
        assert isinstance(data, dict)

    def test_empty_channel_id_in_path_returns_404(self, client):
        # FastAPI path param — empty string produces 404 (no route match)
        resp = client.get("/channel//analytics")
        assert resp.status_code in (404, 422)
