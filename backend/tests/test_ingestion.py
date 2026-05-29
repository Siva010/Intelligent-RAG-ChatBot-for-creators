"""
Unit tests for app/services/ingestion.py

Every external boundary is mocked:
  - yt_dlp.YoutubeDL
  - YouTubeTranscriptApi
  - openai.OpenAI (Whisper API)
  - google.genai.Client (Gemini Files + generate_content)
  - os.path / tempfile (where needed for size checks)

Run with: pytest tests/test_ingestion.py -v
"""
import os
import sys
import json
import types
from unittest.mock import MagicMock, patch, mock_open

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ---------------------------------------------------------------------------
# Helpers to build fake objects returned by SDKs
# ---------------------------------------------------------------------------

def _make_yt_entry(text, start, duration):
    """Dict-style transcript entry (youtube-transcript-api ≥ 0.6)."""
    return {"text": text, "start": start, "duration": duration}


def _make_yt_object_entry(text, start, duration):
    """Object-style transcript entry (some youtube-transcript-api versions)."""
    obj = MagicMock()
    obj.text = text
    obj.start = start
    obj.duration = duration
    return obj


def _fake_ydl_info(**overrides):
    base = {
        "id": "test_vid_id",
        "title": "Test Video Title",
        "description": "A test description",
        "extractor": "youtube",
        "channel": "Test Channel",
        "channel_follower_count": 100_000,
        "tags": ["tag1", "tag2"],
        "upload_date": "20240115",
        "thumbnail": "https://example.com/thumb.jpg",
        "thumbnails": [{"url": "https://example.com/thumb_hq.jpg"}],
        "view_count": 500_000,
        "like_count": 20_000,
        "comment_count": 800,
        "duration": 600,
        "ext": "m4a",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# _description_to_transcript
# ---------------------------------------------------------------------------

class TestDescriptionToTranscript:
    def test_splits_into_15_word_chunks(self):
        from app.services.ingestion import _description_to_transcript
        words = ["word"] * 45
        desc = " ".join(words)
        chunks = _description_to_transcript(desc, "title")
        assert len(chunks) == 3
        for c in chunks:
            assert len(c["text"].split()) == 15

    def test_timing_increments_by_5s(self):
        from app.services.ingestion import _description_to_transcript
        desc = " ".join(["word"] * 30)
        chunks = _description_to_transcript(desc, "title")
        assert chunks[0]["start"] == 0.0
        assert chunks[1]["start"] == 5.0

    def test_empty_description_uses_title(self):
        from app.services.ingestion import _description_to_transcript
        chunks = _description_to_transcript("", "My Title")
        assert len(chunks) >= 1
        assert "My" in chunks[0]["text"] or "Title" in chunks[0]["text"]

    def test_all_chunks_have_5s_duration(self):
        from app.services.ingestion import _description_to_transcript
        chunks = _description_to_transcript("one two three four five six seven eight", "t")
        for c in chunks:
            assert c["duration"] == 5.0


# ---------------------------------------------------------------------------
# _extract_yt_transcript — dict entries path
# ---------------------------------------------------------------------------

class TestExtractYtTranscript:
    @patch("app.services.ingestion.YouTubeTranscriptApi")
    def test_dict_entries_parsed_correctly(self, mock_api):
        from app.services.ingestion import _extract_yt_transcript
        mock_api.get_transcript.return_value = [
            _make_yt_entry("Hello world", 0.0, 3.0),
            _make_yt_entry("Second line", 3.5, 2.5),
        ]
        result = _extract_yt_transcript("dQw4w9WgXcQ")
        assert len(result) == 2
        assert result[0]["text"] == "Hello world"
        assert result[0]["start"] == 0.0
        assert result[1]["duration"] == 2.5

    @patch("app.services.ingestion.YouTubeTranscriptApi")
    def test_object_entries_parsed_correctly(self, mock_api):
        from app.services.ingestion import _extract_yt_transcript
        # Simulate API that returns objects instead of dicts
        del mock_api.get_transcript  # force the hasattr path to fail
        instance = MagicMock()
        instance.fetch.return_value = [
            _make_yt_object_entry("Object entry", 1.0, 4.0),
        ]
        mock_api.return_value = instance
        result = _extract_yt_transcript("abc123")
        assert result[0]["text"] == "Object entry"
        assert result[0]["start"] == 1.0

    @patch("app.services.ingestion.YouTubeTranscriptApi")
    def test_none_text_becomes_empty_string(self, mock_api):
        from app.services.ingestion import _extract_yt_transcript
        mock_api.get_transcript.return_value = [{"text": None, "start": 0.0, "duration": 2.0}]
        result = _extract_yt_transcript("vid")
        assert result[0]["text"] == ""


# ---------------------------------------------------------------------------
# _get_audio_mime_type
# ---------------------------------------------------------------------------

class TestGetAudioMimeType:
    def test_m4a(self):
        from app.services.ingestion import _get_audio_mime_type
        assert _get_audio_mime_type("audio.m4a") == "audio/mp4"

    def test_mp4(self):
        from app.services.ingestion import _get_audio_mime_type
        assert _get_audio_mime_type("file.mp4") == "audio/mp4"

    def test_mp3(self):
        from app.services.ingestion import _get_audio_mime_type
        assert _get_audio_mime_type("clip.mp3") == "audio/mpeg"

    def test_webm(self):
        from app.services.ingestion import _get_audio_mime_type
        assert _get_audio_mime_type("track.webm") == "audio/webm"

    def test_unknown_extension_defaults_to_mp4(self):
        from app.services.ingestion import _get_audio_mime_type
        assert _get_audio_mime_type("audio.xyz") == "audio/mp4"

    def test_uppercase_extension(self):
        from app.services.ingestion import _get_audio_mime_type
        # os.path.splitext preserves case, then .lower() maps .MP3 -> audio/mpeg
        result = _get_audio_mime_type("AUDIO.MP3")
        assert result == "audio/mpeg"


# ---------------------------------------------------------------------------
# _file_state  (Gemini SDK None-safety helper)
# ---------------------------------------------------------------------------

class TestFileState:
    def test_none_state_returns_unknown(self):
        from app.services.ingestion import _file_state
        obj = MagicMock()
        obj.state = None
        assert _file_state(obj) == "UNKNOWN"

    def test_processing_state(self):
        from app.services.ingestion import _file_state
        state = MagicMock()
        state.name = "PROCESSING"
        obj = MagicMock()
        obj.state = state
        assert _file_state(obj) == "PROCESSING"

    def test_active_state(self):
        from app.services.ingestion import _file_state
        state = MagicMock()
        state.name = "ACTIVE"
        obj = MagicMock()
        obj.state = state
        assert _file_state(obj) == "ACTIVE"

    def test_failed_state(self):
        from app.services.ingestion import _file_state
        state = MagicMock()
        state.name = "FAILED"
        obj = MagicMock()
        obj.state = state
        assert _file_state(obj) == "FAILED"

    def test_missing_state_attr(self):
        from app.services.ingestion import _file_state
        obj = types.SimpleNamespace()   # no .state attribute at all
        assert _file_state(obj) == "UNKNOWN"


# ---------------------------------------------------------------------------
# _download_audio_for_asr
# ---------------------------------------------------------------------------

class TestDownloadAudioForAsr:
    @patch("app.services.ingestion.yt_dlp.YoutubeDL")
    def test_returns_path_when_file_exists(self, mock_ydl_cls, tmp_path):
        from app.services.ingestion import _download_audio_for_asr

        # Simulate yt-dlp writing audio.m4a into the tmp dir
        audio_file = tmp_path / "audio.m4a"
        audio_file.write_bytes(b"fake audio data")

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.extract_info.return_value = {"ext": "m4a"}
        mock_ydl_cls.return_value = mock_ctx

        result = _download_audio_for_asr("https://www.instagram.com/reel/abc/", str(tmp_path))
        assert result is not None
        assert result.endswith(".m4a")

    @patch("app.services.ingestion.yt_dlp.YoutubeDL")
    def test_returns_none_on_ydlp_exception(self, mock_ydl_cls, tmp_path):
        from app.services.ingestion import _download_audio_for_asr

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.extract_info.side_effect = Exception("Network error")
        mock_ydl_cls.return_value = mock_ctx

        result = _download_audio_for_asr("https://www.instagram.com/reel/fail/", str(tmp_path))
        assert result is None


# ---------------------------------------------------------------------------
# _transcribe_with_whisper_api
# ---------------------------------------------------------------------------

class TestTranscribeWithWhisperApi:
    def _make_whisper_response(self, segments):
        resp = MagicMock()
        resp.segments = segments
        return resp

    def _make_segment(self, text, start, end):
        seg = MagicMock()
        seg.text = text
        seg.start = start
        seg.end = end
        return seg

    @patch("app.services.ingestion.settings")
    @patch("app.services.ingestion.os.path.getsize")
    @patch("builtins.open", new_callable=mock_open, read_data=b"audio")
    def test_returns_segments_on_success(self, mock_file, mock_size, mock_settings):
        mock_settings.openai_api_key = "sk-test"
        mock_size.return_value = 1024 * 1024  # 1 MB

        seg = self._make_segment("Hello world", 0.0, 2.5)
        whisper_response = self._make_whisper_response([seg])

        with patch("openai.OpenAI") as mock_openai_cls:
            client = MagicMock()
            client.audio.transcriptions.create.return_value = whisper_response
            mock_openai_cls.return_value = client

            from app.services.ingestion import _transcribe_with_whisper_api
            result = _transcribe_with_whisper_api("/tmp/audio.m4a")

        assert result is not None
        assert len(result) == 1
        assert result[0]["text"] == "Hello world"
        assert result[0]["start"] == 0.0
        assert result[0]["duration"] == 2.5

    @patch("app.services.ingestion.settings")
    def test_returns_none_when_no_openai_key(self, mock_settings):
        mock_settings.openai_api_key = ""
        from app.services.ingestion import _transcribe_with_whisper_api
        assert _transcribe_with_whisper_api("/tmp/audio.m4a") is None

    @patch("app.services.ingestion.settings")
    @patch("app.services.ingestion.os.path.getsize")
    def test_returns_none_when_file_too_large(self, mock_size, mock_settings):
        mock_settings.openai_api_key = "sk-test"
        mock_size.return_value = 30 * 1024 * 1024  # 30 MB > 25 MB limit
        from app.services.ingestion import _transcribe_with_whisper_api
        assert _transcribe_with_whisper_api("/tmp/big.m4a") is None

    @patch("app.services.ingestion.settings")
    @patch("app.services.ingestion.os.path.getsize")
    @patch("builtins.open", new_callable=mock_open, read_data=b"audio")
    def test_returns_none_on_api_exception(self, mock_file, mock_size, mock_settings):
        mock_settings.openai_api_key = "sk-test"
        mock_size.return_value = 1024

        with patch("openai.OpenAI") as mock_openai_cls:
            client = MagicMock()
            client.audio.transcriptions.create.side_effect = Exception("API error")
            mock_openai_cls.return_value = client

            from app.services.ingestion import _transcribe_with_whisper_api
            result = _transcribe_with_whisper_api("/tmp/audio.m4a")

        assert result is None

    @patch("app.services.ingestion.settings")
    @patch("app.services.ingestion.os.path.getsize")
    @patch("builtins.open", new_callable=mock_open, read_data=b"audio")
    def test_strips_empty_segment_text(self, mock_file, mock_size, mock_settings):
        mock_settings.openai_api_key = "sk-test"
        mock_size.return_value = 1024

        seg_empty = self._make_segment("   ", 0.0, 2.0)
        seg_valid = self._make_segment("Real words", 2.0, 4.0)
        response = self._make_whisper_response([seg_empty, seg_valid])

        with patch("openai.OpenAI") as mock_openai_cls:
            client = MagicMock()
            client.audio.transcriptions.create.return_value = response
            mock_openai_cls.return_value = client

            from app.services.ingestion import _transcribe_with_whisper_api
            result = _transcribe_with_whisper_api("/tmp/audio.m4a")

        # Empty segment must be filtered out
        assert result is not None
        assert len(result) == 1
        assert result[0]["text"] == "Real words"


# ---------------------------------------------------------------------------
# _transcribe_with_gemini_audio
# ---------------------------------------------------------------------------

def _make_gemini_client(state_name="ACTIVE", file_name="files/abc123",
                        transcript_json=None, generate_raises=None):
    """Build a fully mocked google.genai.Client for ASR tests."""
    if transcript_json is None:
        transcript_json = json.dumps([
            {"text": "Hey everyone", "start": 0.0, "duration": 2.0},
            {"text": "Welcome to the channel", "start": 2.0, "duration": 3.0},
        ])

    # File object returned by upload() and get()
    state_obj = MagicMock()
    state_obj.name = state_name

    file_obj = MagicMock()
    file_obj.name = file_name
    file_obj.state = state_obj
    file_obj.mime_type = "audio/mp4"
    file_obj.uri = "https://generativelanguage.googleapis.com/files/abc123"

    client = MagicMock()
    client.files.upload.return_value = file_obj
    client.files.get.return_value = file_obj   # polling returns same ACTIVE file
    client.files.delete.return_value = None

    gen_response = MagicMock()
    gen_response.text = transcript_json
    if generate_raises:
        client.models.generate_content.side_effect = generate_raises
    else:
        client.models.generate_content.return_value = gen_response

    return client, file_obj


class TestTranscribeWithGeminiAudio:
    @patch("app.services.ingestion.settings")
    @patch("app.services.ingestion.os.path.getsize", return_value=512_000)
    @patch("builtins.open", new_callable=mock_open, read_data=b"audio")
    def test_success_path_returns_segments(self, mock_file, mock_size, mock_settings):
        mock_settings.google_api_key = "AIza-test"

        client, _ = _make_gemini_client()
        with patch("google.genai.Client") as mock_client_cls:
            mock_client_cls.return_value = client

            from app.services.ingestion import _transcribe_with_gemini_audio
            result = _transcribe_with_gemini_audio("/tmp/audio.m4a")

        assert result is not None
        assert len(result) == 2
        assert result[0]["text"] == "Hey everyone"
        assert result[0]["start"] == 0.0
        assert result[1]["duration"] == 3.0

    @patch("app.services.ingestion.settings")
    def test_returns_none_when_no_google_key(self, mock_settings):
        mock_settings.google_api_key = ""
        from app.services.ingestion import _transcribe_with_gemini_audio
        assert _transcribe_with_gemini_audio("/tmp/audio.m4a") is None

    @patch("app.services.ingestion.settings")
    @patch("app.services.ingestion.os.path.getsize", return_value=512_000)
    @patch("builtins.open", new_callable=mock_open, read_data=b"audio")
    def test_returns_none_when_file_name_is_none(self, mock_file, mock_size, mock_settings):
        """upload() returns a File with name=None → bail early."""
        mock_settings.google_api_key = "AIza-test"

        client, file_obj = _make_gemini_client()
        file_obj.name = None   # SDK returns None name

        with patch("google.genai.Client") as mock_client_cls:
            mock_client_cls.return_value = client

            from app.services.ingestion import _transcribe_with_gemini_audio
            result = _transcribe_with_gemini_audio("/tmp/audio.m4a")

        assert result is None

    @patch("app.services.ingestion.settings")
    @patch("app.services.ingestion.os.path.getsize", return_value=512_000)
    @patch("builtins.open", new_callable=mock_open, read_data=b"audio")
    def test_returns_none_when_state_never_becomes_active(self, mock_file, mock_size, mock_settings):
        """File stays FAILED after polling → bail."""
        mock_settings.google_api_key = "AIza-test"

        client, _ = _make_gemini_client(state_name="FAILED")

        with patch("app.services.ingestion.time.time") as mock_time, \
             patch("app.services.ingestion.time.sleep"), \
             patch("google.genai.Client") as mock_client_cls:
            # Time immediately exceeds deadline so loop exits after first check
            mock_time.side_effect = [0, 100, 100]
            mock_client_cls.return_value = client

            from app.services.ingestion import _transcribe_with_gemini_audio
            result = _transcribe_with_gemini_audio("/tmp/audio.m4a")

        assert result is None

    @patch("app.services.ingestion.settings")
    @patch("app.services.ingestion.os.path.getsize", return_value=512_000)
    @patch("builtins.open", new_callable=mock_open, read_data=b"audio")
    def test_none_initial_state_polls_then_becomes_active(self, mock_file, mock_size, mock_settings):
        """state=None on first response (UNKNOWN) → polls once → ACTIVE → success."""
        mock_settings.google_api_key = "AIza-test"

        state_none = MagicMock()
        state_none.name = None   # state is an object but .name is None
        state_active = MagicMock()
        state_active.name = "ACTIVE"

        file_initial = MagicMock()
        file_initial.name = "files/abc"
        file_initial.state = None     # None state on first upload response

        file_polled = MagicMock()
        file_polled.name = "files/abc"
        file_polled.state = state_active
        file_polled.uri = "uri"
        file_polled.mime_type = "audio/mp4"

        segments_json = json.dumps([{"text": "Polled content", "start": 0.0, "duration": 2.0}])
        gen_response = MagicMock()
        gen_response.text = segments_json

        client = MagicMock()
        client.files.upload.return_value = file_initial
        client.files.get.return_value = file_polled
        client.files.delete.return_value = None
        client.models.generate_content.return_value = gen_response

        with patch("app.services.ingestion.time.sleep"), \
             patch("google.genai.Client") as mock_client_cls:
            mock_client_cls.return_value = client

            from app.services.ingestion import _transcribe_with_gemini_audio
            result = _transcribe_with_gemini_audio("/tmp/audio.m4a")

        assert result is not None
        assert result[0]["text"] == "Polled content"

    @patch("app.services.ingestion.settings")
    @patch("app.services.ingestion.os.path.getsize", return_value=512_000)
    @patch("builtins.open", new_callable=mock_open, read_data=b"audio")
    def test_remote_file_deleted_after_success(self, mock_file, mock_size, mock_settings):
        mock_settings.google_api_key = "AIza-test"
        client, _ = _make_gemini_client()

        with patch("google.genai.Client") as mock_client_cls:
            mock_client_cls.return_value = client

            from app.services.ingestion import _transcribe_with_gemini_audio
            _transcribe_with_gemini_audio("/tmp/audio.m4a")

        client.files.delete.assert_called_once_with(name="files/abc123")


# ---------------------------------------------------------------------------
# _asr_transcribe  (orchestrator)
# ---------------------------------------------------------------------------

class TestAsrTranscribe:
    def test_whisper_wins_when_available(self):
        whisper_segments = [{"text": "Whisper words", "start": 0.0, "duration": 3.0}]

        with patch("app.services.ingestion._download_audio_for_asr", return_value="/tmp/audio.m4a"), \
             patch("app.services.ingestion.settings") as mock_settings, \
             patch("app.services.ingestion._transcribe_with_whisper_api", return_value=whisper_segments):
            mock_settings.openai_api_key = "sk-test"
            mock_settings.google_api_key = "AIza-test"

            from app.services.ingestion import _asr_transcribe
            segments, method = _asr_transcribe("https://www.instagram.com/reel/abc/")

        assert method == "whisper"
        assert segments[0]["text"] == "Whisper words"

    def test_gemini_used_when_whisper_fails(self):
        gemini_segments = [{"text": "Gemini words", "start": 0.0, "duration": 3.0}]

        with patch("app.services.ingestion._download_audio_for_asr", return_value="/tmp/audio.m4a"), \
             patch("app.services.ingestion.settings") as mock_settings, \
             patch("app.services.ingestion._transcribe_with_whisper_api", return_value=None), \
             patch("app.services.ingestion._transcribe_with_gemini_audio", return_value=gemini_segments):
            mock_settings.openai_api_key = "sk-test"
            mock_settings.google_api_key = "AIza-test"

            from app.services.ingestion import _asr_transcribe
            segments, method = _asr_transcribe("https://www.tiktok.com/@user/video/123")

        assert method == "gemini"
        assert segments[0]["text"] == "Gemini words"

    def test_description_fallback_when_audio_download_fails(self):
        with patch("app.services.ingestion._download_audio_for_asr", return_value=None), \
             patch("app.services.ingestion.settings") as mock_settings:
            mock_settings.openai_api_key = "sk-test"
            mock_settings.google_api_key = "AIza-test"

            from app.services.ingestion import _asr_transcribe
            segments, method = _asr_transcribe("https://www.instagram.com/reel/fail/")

        assert method == "description"
        assert segments == []

    def test_description_fallback_when_both_asr_fail(self):
        with patch("app.services.ingestion._download_audio_for_asr", return_value="/tmp/audio.m4a"), \
             patch("app.services.ingestion.settings") as mock_settings, \
             patch("app.services.ingestion._transcribe_with_whisper_api", return_value=None), \
             patch("app.services.ingestion._transcribe_with_gemini_audio", return_value=None):
            mock_settings.openai_api_key = "sk-test"
            mock_settings.google_api_key = "AIza-test"

            from app.services.ingestion import _asr_transcribe
            segments, method = _asr_transcribe("https://www.tiktok.com/@user/video/fail")

        assert method == "description"
        assert segments == []


# ---------------------------------------------------------------------------
# RealMediaIngestor.ingest — YouTube path
# ---------------------------------------------------------------------------

class TestRealMediaIngestorYouTube:
    def _patch_ydl(self, info: dict):
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.extract_info.return_value = info
        return mock_ctx

    @patch("app.services.ingestion.yt_dlp.YoutubeDL")
    @patch("app.services.ingestion.YouTubeTranscriptApi")
    def test_youtube_ingest_returns_normalized_schema(self, mock_api, mock_ydl_cls):
        mock_ydl_cls.return_value = self._patch_ydl(_fake_ydl_info())
        mock_api.get_transcript.return_value = [
            _make_yt_entry("First line", 0.0, 3.0),
            _make_yt_entry("Second line", 3.0, 4.0),
        ]

        from app.services.ingestion import RealMediaIngestor
        result = RealMediaIngestor().ingest("https://www.youtube.com/watch?v=test_vid_id")

        assert result["video_id"] == "test_vid_id"
        assert result["title"] == "Test Video Title"
        assert result["platform"] == "youtube"
        assert result["asr_method"] == "youtube_captions"
        assert result["whisper_stubbed"] is False
        assert len(result["transcript"]) == 2
        assert result["metrics"]["views"] == 500_000
        assert result["engagement_rate"] > 0

    @patch("app.services.ingestion.yt_dlp.YoutubeDL")
    @patch("app.services.ingestion.YouTubeTranscriptApi")
    def test_youtube_upload_date_formatted(self, mock_api, mock_ydl_cls):
        mock_ydl_cls.return_value = self._patch_ydl(_fake_ydl_info(upload_date="20240315"))
        mock_api.get_transcript.return_value = [_make_yt_entry("Hi", 0.0, 2.0)]

        from app.services.ingestion import RealMediaIngestor
        result = RealMediaIngestor().ingest("https://www.youtube.com/watch?v=test")
        assert result["upload_date"] == "2024-03-15"

    @patch("app.services.ingestion.yt_dlp.YoutubeDL")
    @patch("app.services.ingestion.YouTubeTranscriptApi")
    def test_youtube_transcript_failure_sets_whisper_stubbed(self, mock_api, mock_ydl_cls):
        mock_ydl_cls.return_value = self._patch_ydl(_fake_ydl_info())
        mock_api.get_transcript.side_effect = Exception("Transcript disabled")

        from app.services.ingestion import RealMediaIngestor
        result = RealMediaIngestor().ingest("https://www.youtube.com/watch?v=test")

        assert result["whisper_stubbed"] is True
        assert result["asr_method"] == "description"

    @patch("app.services.ingestion.yt_dlp.YoutubeDL")
    @patch("app.services.ingestion.YouTubeTranscriptApi")
    def test_instagram_views_estimated_from_likes(self, mock_api, mock_ydl_cls):
        info = _fake_ydl_info(
            extractor="instagram",
            view_count=None,
            like_count=5000,
            comment_count=100,
        )
        mock_ydl_cls.return_value = self._patch_ydl(info)

        with patch("app.services.ingestion._asr_transcribe") as mock_asr:
            mock_asr.return_value = ([{"text": "hey", "start": 0.0, "duration": 2.0}], "gemini")
            from app.services.ingestion import RealMediaIngestor
            result = RealMediaIngestor().ingest("https://www.instagram.com/reel/abc/")

        assert result["is_estimated_views"] is True
        assert result["metrics"]["views"] == 5000 * 20

    @patch("app.services.ingestion.yt_dlp.YoutubeDL")
    def test_ingest_raises_when_ydlp_fails_completely(self, mock_ydl_cls):
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.extract_info.side_effect = Exception("Network error")
        mock_ydl_cls.return_value = mock_ctx

        from app.services.ingestion import RealMediaIngestor
        with pytest.raises(RuntimeError, match="Could not fetch data"):
            RealMediaIngestor().ingest("https://www.instagram.com/reel/broken/")

    @patch("app.services.ingestion.yt_dlp.YoutubeDL")
    @patch("app.services.ingestion.YouTubeTranscriptApi")
    def test_asr_method_set_to_gemini_for_instagram(self, mock_api, mock_ydl_cls):
        info = _fake_ydl_info(extractor="instagram")
        mock_ydl_cls.return_value = self._patch_ydl(info)
        gemini_segments = [{"text": "Real speech", "start": 0.0, "duration": 3.0}]

        with patch("app.services.ingestion._asr_transcribe") as mock_asr:
            mock_asr.return_value = (gemini_segments, "gemini")
            from app.services.ingestion import RealMediaIngestor
            result = RealMediaIngestor().ingest("https://www.instagram.com/reel/abc/")

        assert result["asr_method"] == "gemini"
        assert result["whisper_stubbed"] is False
        assert result["transcript"][0]["text"] == "Real speech"
