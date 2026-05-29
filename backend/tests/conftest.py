"""
Shared pytest fixtures for the CreatorJoy backend test suite.
All API boundaries are stubbed — no real network calls, no running server.
"""
import sys
import os

# Ensure backend/ is always importable regardless of where pytest is invoked from
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


# ---------------------------------------------------------------------------
# Re-usable video data fixtures
# ---------------------------------------------------------------------------

SAMPLE_TRANSCRIPT = [
    {"text": "Welcome back everyone", "start": 0.0, "duration": 3.0},
    {"text": "Today we cover something huge", "start": 3.0, "duration": 4.0},
    {"text": "This one trick changed everything", "start": 7.0, "duration": 5.0},
    # body (>= 15 s)
    {"text": "Let me explain the first concept", "start": 15.0, "duration": 4.0},
    {"text": "The second point is critical", "start": 19.0, "duration": 4.0},
    {"text": "And here is the key takeaway", "start": 23.0, "duration": 5.0},
]


@pytest.fixture
def sample_transcript():
    return list(SAMPLE_TRANSCRIPT)


@pytest.fixture
def sample_video_a():
    return {
        "video_id": "vid_a",
        "title": "How I 10x My Revenue",
        "platform": "youtube",
        "creator": "Creator Alpha",
        "follower_count": 500_000,
        "hashtags": ["#business", "#growth"],
        "upload_date": "2024-01-15",
        "thumbnail_url": "https://img.youtube.com/vi/vid_a/maxresdefault.jpg",
        "metrics": {"views": 1_200_000, "likes": 48_000, "comments": 1_800, "duration": 720},
        "engagement_rate": 4.15,
        "is_estimated_views": False,
        "whisper_stubbed": False,
        "asr_method": "youtube_captions",
        "transcript": list(SAMPLE_TRANSCRIPT),
    }


@pytest.fixture
def sample_video_b():
    return {
        "video_id": "vid_b",
        "title": "Secret Growth Hack Revealed",
        "platform": "youtube",
        "creator": "Creator Beta",
        "follower_count": 120_000,
        "hashtags": ["#growth", "#hack"],
        "upload_date": "2024-02-20",
        "thumbnail_url": "https://img.youtube.com/vi/vid_b/maxresdefault.jpg",
        "metrics": {"views": 300_000, "likes": 24_000, "comments": 600, "duration": 480},
        "engagement_rate": 8.20,
        "is_estimated_views": False,
        "whisper_stubbed": False,
        "asr_method": "youtube_captions",
        "transcript": [
            {"text": "This secret will shock you", "start": 0.0, "duration": 4.0},
            {"text": "Nobody talks about this growth hack", "start": 4.0, "duration": 5.0},
            {"text": "Here is how it works in practice", "start": 15.0, "duration": 6.0},
        ],
    }
