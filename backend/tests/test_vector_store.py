"""
Unit tests for the VectorStoreManager and related helpers.
Run with: pytest tests/test_vector_store.py -v
"""
import sys
import os

# Ensure the backend/ directory is on the path so imports work without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.services.vector_store import VectorStoreManager, SimpleVectorStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def store():
    return VectorStoreManager()


SAMPLE_TRANSCRIPT = [
    {"text": "Welcome back everyone", "start": 0.0, "duration": 3.0},
    {"text": "Today we are going to cover something really important", "start": 3.0, "duration": 5.0},
    {"text": "This single thing changed my business", "start": 8.0, "duration": 4.0},
    # body starts at 15s
    {"text": "Let me explain the first concept right now", "start": 15.0, "duration": 4.0},
    {"text": "The second point is even more critical", "start": 19.0, "duration": 4.0},
]

# Generate enough body entries to trigger a full 350-word chunk
LONG_BODY = [
    {"text": " ".join([f"word{i}" for i in range(j * 20, (j + 1) * 20)]), "start": 15.0 + j * 5.0, "duration": 5.0}
    for j in range(20)  # 20 entries × 20 words = 400 words total body
]
LONG_TRANSCRIPT = SAMPLE_TRANSCRIPT[:3] + LONG_BODY


# ---------------------------------------------------------------------------
# isolate_hooks
# ---------------------------------------------------------------------------

class TestIsolateHooks:
    def test_returns_only_first_15s(self, store):
        hook = store.isolate_hooks(SAMPLE_TRANSCRIPT)
        assert "Welcome back everyone" in hook
        assert "Today we are going to cover" in hook
        assert "This single thing changed my business" in hook
        # body entries must NOT be in the hook
        assert "Let me explain" not in hook

    def test_empty_transcript(self, store):
        assert store.isolate_hooks([]) == ""

    def test_no_entries_before_15s(self, store):
        transcript = [{"text": "Starts late", "start": 20.0, "duration": 3.0}]
        assert store.isolate_hooks(transcript) == ""


# ---------------------------------------------------------------------------
# chunk_transcript
# ---------------------------------------------------------------------------

class TestChunkTranscript:
    def test_hook_chunk_is_always_included(self, store):
        chunks = store.chunk_transcript(SAMPLE_TRANSCRIPT, "vid_a")
        hook_chunks = [c for c in chunks if c.get("is_hook")]
        assert len(hook_chunks) == 1, "Expected exactly one hook chunk"
        assert hook_chunks[0]["start"] == 0.0
        assert "Welcome back" in hook_chunks[0]["text"]

    def test_body_chunks_have_is_hook_false(self, store):
        chunks = store.chunk_transcript(SAMPLE_TRANSCRIPT, "vid_a")
        body_chunks = [c for c in chunks if not c.get("is_hook")]
        for c in body_chunks:
            assert c.get("is_hook") is False

    def test_body_chunks_start_at_or_after_15s(self, store):
        chunks = store.chunk_transcript(SAMPLE_TRANSCRIPT, "vid_a")
        body_chunks = [c for c in chunks if not c.get("is_hook")]
        for c in body_chunks:
            assert c["start"] >= 15.0

    def test_empty_transcript_returns_empty_list(self, store):
        chunks = store.chunk_transcript([], "vid_empty")
        assert chunks == []

    def test_transcript_with_only_hook_entries(self, store):
        """If all entries are before 15s, should return only the hook chunk."""
        transcript = [
            {"text": "Quick tip", "start": 0.0, "duration": 5.0},
            {"text": "Subscribe now", "start": 5.0, "duration": 5.0},
        ]
        chunks = store.chunk_transcript(transcript, "short_vid")
        assert len(chunks) == 1
        assert chunks[0]["is_hook"] is True

    def test_large_transcript_creates_multiple_body_chunks(self, store):
        chunks = store.chunk_transcript(LONG_TRANSCRIPT, "vid_long")
        body_chunks = [c for c in chunks if not c.get("is_hook")]
        assert len(body_chunks) >= 1, "400-word body should produce at least 1 body chunk"

    def test_video_id_is_set_on_all_chunks(self, store):
        chunks = store.chunk_transcript(SAMPLE_TRANSCRIPT, "test_video_id")
        for c in chunks:
            assert c["video_id"] == "test_video_id"


# ---------------------------------------------------------------------------
# SimpleVectorStore — video_id filtering
# ---------------------------------------------------------------------------

class TestSimpleVectorStoreFiltering:
    def test_returns_only_matching_video_ids(self):
        svs = SimpleVectorStore()
        svs.add_documents(
            texts=["This is about cooking recipes", "Stock market tips and investing"],
            metadatas=[{"video_id": "vid_a"}, {"video_id": "vid_b"}],
            ids=["vid_a_chunk_0", "vid_b_chunk_0"],
        )
        results = svs.query("cooking", n_results=5, video_ids=["vid_a"])
        returned_ids = results["metadatas"][0]
        for meta in returned_ids:
            assert meta["video_id"] == "vid_a", "Should only return vid_a chunks"

    def test_no_filter_returns_all(self):
        svs = SimpleVectorStore()
        svs.add_documents(
            texts=["Content from video A", "Content from video B"],
            metadatas=[{"video_id": "vid_a"}, {"video_id": "vid_b"}],
            ids=["vid_a_0", "vid_b_0"],
        )
        results = svs.query("content video", n_results=5)
        assert len(results["documents"][0]) == 2

    def test_empty_results_when_no_video_matches(self):
        svs = SimpleVectorStore()
        svs.add_documents(
            texts=["Some content here"],
            metadatas=[{"video_id": "vid_x"}],
            ids=["vid_x_0"],
        )
        results = svs.query("some content", n_results=5, video_ids=["vid_y"])
        assert results["documents"][0] == []


# ---------------------------------------------------------------------------
# Mock hook analysis (no API key needed)
# ---------------------------------------------------------------------------

class TestMockHookAnalysis:
    def test_mock_hook_analysis_contains_winner(self):
        """_generate_mock_hook_analysis should declare a winner between A and B."""
        from app.services.agent import _generate_mock_hook_analysis

        video_a = {
            "video_id": "va", "title": "Video Alpha", "platform": "youtube",
            "engagement_rate": 3.5,
            "transcript": [{"text": "Fast paced hook here", "start": 0.0, "duration": 5.0}],
            "metrics": {"views": 100000, "likes": 3500, "comments": 200},
        }
        video_b = {
            "video_id": "vb", "title": "Video Beta", "platform": "youtube",
            "engagement_rate": 8.0,
            "transcript": [{"text": "Emotional curiosity driven opener", "start": 0.0, "duration": 5.0}],
            "metrics": {"views": 200000, "likes": 16000, "comments": 500},
        }

        result = _generate_mock_hook_analysis(video_a, video_b)

        assert "Winner Verdict" in result
        # Higher engagement video_b should win
        assert "Video B" in result
        assert "8.0%" in result

    def test_mock_hook_analysis_flips_winner_correctly(self):
        from app.services.agent import _generate_mock_hook_analysis

        video_a = {
            "video_id": "va", "title": "Alpha", "platform": "youtube",
            "engagement_rate": 12.0,
            "transcript": [{"text": "A great hook", "start": 0.0, "duration": 5.0}],
            "metrics": {"views": 500000, "likes": 60000, "comments": 1000},
        }
        video_b = {
            "video_id": "vb", "title": "Beta", "platform": "youtube",
            "engagement_rate": 2.0,
            "transcript": [{"text": "A weak opening", "start": 0.0, "duration": 5.0}],
            "metrics": {"views": 100000, "likes": 2000, "comments": 100},
        }

        result = _generate_mock_hook_analysis(video_a, video_b)
        assert "Video A" in result
        assert "12.0%" in result
