import re
import os
import json
import time
import tempfile
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

from app.config import settings

logger = logging.getLogger(__name__)

COOKIES_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'cookies.txt')
COOKIES_FILE = os.path.normpath(COOKIES_FILE)

# Whisper API file-size cap (25 MB hard limit imposed by OpenAI)
WHISPER_MAX_BYTES = 25 * 1024 * 1024


class BaseIngestor(ABC):
    @abstractmethod
    def ingest(self, url: str) -> Dict[str, Any]:
        """
        Accepts a video URL, extracts its transcript and metrics,
        and returns a normalized JSON schema.
        """
        pass


def _build_ydl_opts(with_cookies: bool = True) -> Dict[str, Any]:
    """Build yt-dlp options, optionally including a cookies.txt file."""
    opts: Dict[str, Any] = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    if with_cookies and os.path.isfile(COOKIES_FILE):
        opts['cookiefile'] = COOKIES_FILE
        logger.info(f"Using cookies.txt at: {COOKIES_FILE}")
    return opts


def _extract_yt_transcript(video_id: str) -> List[Dict[str, Any]]:
    """Fetch YouTube transcript via youtube-transcript-api."""
    if hasattr(YouTubeTranscriptApi, 'get_transcript'):
        get_t: Any = getattr(YouTubeTranscriptApi, 'get_transcript')
        raw = get_t(video_id, languages=['en', 'hi', 'en-US', 'en-GB'])
    else:
        api_instance = YouTubeTranscriptApi()
        raw = api_instance.fetch(video_id, languages=['en', 'hi', 'en-US', 'en-GB'])

    result = []
    for entry in raw:
        if isinstance(entry, dict):
            text = entry.get("text", "")
            start = entry.get("start", 0.0)
            dur = entry.get("duration", 0.0)
        else:
            text = getattr(entry, "text", "")
            start = getattr(entry, "start", 0.0)
            dur = getattr(entry, "duration", 0.0)
        result.append({
            "text": text or "",
            "start": round(float(start or 0.0), 2),
            "duration": round(float(dur or 0.0), 2),
        })
    return result


def _description_to_transcript(description: str, title: str) -> List[Dict[str, Any]]:
    """Convert a post caption/description into pseudo-transcript chunks."""
    text = description or title
    words = text.split()
    chunk_size = 15
    current_time = 0.0
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunk_text = " ".join(words[i:i + chunk_size])
        chunks.append({"text": chunk_text, "start": current_time, "duration": 5.0})
        current_time += 5.0
    if not chunks:
        chunks = [{"text": title, "start": 0.0, "duration": 5.0}]
    return chunks


# ---------------------------------------------------------------------------
# ASR helpers
# ---------------------------------------------------------------------------

def _get_audio_mime_type(path: str) -> str:
    """Map a file extension to a MIME type accepted by the Gemini Files API."""
    return {
        '.mp4': 'audio/mp4',
        '.m4a': 'audio/mp4',
        '.mp3': 'audio/mpeg',
        '.webm': 'audio/webm',
        '.wav': 'audio/wav',
        '.ogg': 'audio/ogg',
    }.get(os.path.splitext(path)[1].lower(), 'audio/mp4')


def _download_audio_for_asr(url: str, output_dir: str) -> Optional[str]:
    """
    Download the audio track of a video URL into *output_dir* using yt-dlp.

    Prefers native container formats that require no FFmpeg post-processing
    (m4a → mp4 → webm) so the pipeline works on machines without FFmpeg.
    Returns the absolute path to the downloaded file, or None on failure.
    """
    base_path = os.path.join(output_dir, "audio")

    # Format string: prefer audio-only m4a, fallback to mp4/webm, then best.
    # Filesize filter avoids downloading huge files before the API size check.
    format_str = (
        'bestaudio[ext=m4a][filesize<25M]'
        '/bestaudio[ext=mp4][filesize<25M]'
        '/bestaudio[ext=webm][filesize<25M]'
        '/bestaudio[filesize<25M]'
        '/best[filesize<25M]'
    )

    opts: Dict[str, Any] = {
        'format': format_str,
        'outtmpl': base_path + '.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'skip_download': False,
    }
    if os.path.isfile(COOKIES_FILE):
        opts['cookiefile'] = COOKIES_FILE

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore[arg-type]
            info = ydl.extract_info(url, download=True) or {}
            ext = info.get('ext', '')
            # Check the expected path first
            candidate = f"{base_path}.{ext}"
            if os.path.isfile(candidate):
                size_mb = os.path.getsize(candidate) / 1024 / 1024
                logger.info(f"Audio downloaded: {candidate} ({size_mb:.1f} MB)")
                return candidate

        # yt-dlp sometimes writes a different extension; scan the directory
        for fname in os.listdir(output_dir):
            if fname.startswith("audio."):
                full = os.path.join(output_dir, fname)
                size_mb = os.path.getsize(full) / 1024 / 1024
                logger.info(f"Audio discovered: {full} ({size_mb:.1f} MB)")
                return full

        logger.warning("Audio download succeeded but file not found in output dir.")
        return None

    except Exception as e:
        logger.warning(f"Audio download failed for ASR ({url}): {e}")
        return None


def _transcribe_with_whisper_api(audio_path: str) -> Optional[List[Dict[str, Any]]]:
    """
    Transcribe an audio file using the OpenAI Whisper API.

    Returns a list of {text, start, duration} dicts (same schema as YouTube
    transcripts) or None on any failure.
    Requires settings.openai_api_key to be set.
    """
    if not settings.openai_api_key:
        return None

    file_size = os.path.getsize(audio_path)
    if file_size > WHISPER_MAX_BYTES:
        logger.warning(
            f"Audio file exceeds Whisper 25 MB limit "
            f"({file_size / 1024 / 1024:.1f} MB) — skipping Whisper."
        )
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)

        logger.info(f"Calling Whisper API on {audio_path} ({file_size // 1024} KB)…")
        with open(audio_path, 'rb') as audio_file:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )

        raw_segments = getattr(response, 'segments', None) or []
        result: List[Dict[str, Any]] = []
        for seg in raw_segments:
            text = getattr(seg, 'text', '').strip()
            start = float(getattr(seg, 'start', 0.0))
            end = float(getattr(seg, 'end', start))
            if text:
                result.append({
                    "text": text,
                    "start": round(start, 2),
                    "duration": round(max(end - start, 0.0), 2),
                })

        if result:
            logger.info(f"Whisper API returned {len(result)} segments.")
            return result

        logger.warning("Whisper API returned an empty transcript.")
        return None

    except Exception as e:
        logger.error(f"Whisper API transcription failed: {e}")
        return None


def _file_state(file_obj: Any) -> str:
    """
    Safely extract the state name from a Gemini File object.

    The google-genai SDK can return a File whose .state is None immediately
    after upload (the field is not always populated on the first response).
    Returning 'UNKNOWN' lets the caller treat it like PROCESSING and poll again.
    """
    state = getattr(file_obj, 'state', None)
    if state is None:
        return 'UNKNOWN'
    return getattr(state, 'name', str(state))


def _transcribe_with_gemini_audio(audio_path: str) -> Optional[List[Dict[str, Any]]]:
    """
    Transcribe an audio file using Gemini 2.5 Flash's native audio understanding.

    Uploads the file via the Gemini Files API, waits for it to become ACTIVE,
    then prompts the model for a timestamped JSON transcript.
    Forces JSON output via response_mime_type to avoid parsing fragility.
    Cleans up the uploaded file afterward.

    Returns a list of {text, start, duration} dicts or None on any failure.
    Requires settings.google_api_key to be set.
    """
    if not settings.google_api_key:
        return None

    try:
        from google import genai as google_genai
        from google.genai import types as genai_types

        client = google_genai.Client(api_key=settings.google_api_key)
        mime = _get_audio_mime_type(audio_path)
        size_mb = os.path.getsize(audio_path) / 1024 / 1024
        logger.info(f"Uploading audio to Gemini Files API: {audio_path} ({size_mb:.1f} MB, {mime})")

        # --- Upload ---
        with open(audio_path, 'rb') as f:
            uploaded = client.files.upload(
                file=f,
                config=genai_types.UploadFileConfig(
                    display_name="asr_audio",
                    mime_type=mime,
                ),
            )

        # Bail early if the SDK didn't return a file name (should never happen
        # for a successful upload, but the field is typed Optional[str]).
        file_name: str = uploaded.name or ""
        if not file_name:
            logger.error("Gemini Files API returned a file with no name. Skipping Gemini ASR.")
            return None

        # --- Poll until ACTIVE (max 90 s) ---
        # _file_state() guards against .state being None right after upload.
        # Treat UNKNOWN (None state) the same as PROCESSING — poll again.
        deadline = time.time() + 90
        while _file_state(uploaded) in ('PROCESSING', 'UNKNOWN') and time.time() < deadline:
            time.sleep(3)
            uploaded = client.files.get(name=file_name)

        current_state = _file_state(uploaded)
        if current_state != 'ACTIVE':
            logger.error(
                f"Gemini file never became ACTIVE (state={current_state}). "
                "Skipping Gemini ASR."
            )
            try:
                client.files.delete(name=file_name)
            except Exception:
                pass
            return None

        # --- Transcription prompt ---
        prompt = (
            "Transcribe every spoken word in this audio with accurate timestamps.\n"
            "Return ONLY a JSON array where each element has exactly these keys:\n"
            '  "text"     : the spoken words in this segment (string)\n'
            '  "start"    : start time in seconds from the beginning (float)\n'
            '  "duration" : length of this segment in seconds (float)\n'
            "Group words into natural sentence-length segments (roughly 5–20 words each).\n"
            "If there is no audible speech, return an empty array: []"
        )

        logger.info("Sending audio to Gemini 2.5 Flash for transcription…")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[uploaded, prompt],
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )

        # --- Clean up remote file ---
        try:
            client.files.delete(name=file_name)
        except Exception:
            pass

        # --- Parse response ---
        raw_text = (response.text or "").strip()
        segments_raw = json.loads(raw_text)
        if not isinstance(segments_raw, list):
            logger.warning("Gemini ASR: response was not a JSON list.")
            return None

        result: List[Dict[str, Any]] = []
        for seg in segments_raw:
            text = str(seg.get('text', '')).strip()
            if text:
                result.append({
                    "text": text,
                    "start": round(float(seg.get('start', 0.0)), 2),
                    "duration": round(float(seg.get('duration', 3.0)), 2),
                })

        if result:
            logger.info(f"Gemini ASR returned {len(result)} segments.")
            return result

        logger.warning("Gemini ASR returned an empty transcript.")
        return None

    except Exception as e:
        logger.error(f"Gemini audio transcription failed: {e}")
        return None


def _asr_transcribe(url: str) -> Tuple[List[Dict[str, Any]], str]:
    """
    Orchestrate the 3-tier ASR cascade for a non-YouTube video URL.

    Priority:
      1. OpenAI Whisper API  (requires OPENAI_API_KEY)
      2. Gemini 2.5 Flash    (requires GOOGLE_API_KEY)
      3. Description pseudo-transcript (always available, worst quality)

    Returns:
        (transcript_data, method_name) where method_name is one of:
        "whisper" | "gemini" | "description"
    """
    with tempfile.TemporaryDirectory(prefix="cj_asr_") as tmp_dir:
        audio_path = _download_audio_for_asr(url, tmp_dir)

        if audio_path:
            # Tier 1: Whisper (preferred — purpose-built ASR with native timestamps)
            if settings.openai_api_key:
                result = _transcribe_with_whisper_api(audio_path)
                if result:
                    return result, "whisper"

            # Tier 2: Gemini audio (no extra key needed beyond GOOGLE_API_KEY)
            if settings.google_api_key:
                result = _transcribe_with_gemini_audio(audio_path)
                if result:
                    return result, "gemini"

        # temp dir is cleaned up here regardless of outcome

    logger.warning(f"ASR cascade exhausted for {url} — falling back to description.")
    return [], "description"


# ---------------------------------------------------------------------------
# Ingestor
# ---------------------------------------------------------------------------

class RealMediaIngestor(BaseIngestor):
    """
    Universal ingestor that uses yt-dlp to fetch real metadata for YouTube,
    Instagram Reels, and TikTok. Falls back gracefully at each step.
    """

    def _fetch_info(self, url: str) -> Dict[str, Any]:
        """Try yt-dlp with cookies first, then without."""
        # Attempt 1: with cookies.txt (if available)
        try:
            opts = _build_ydl_opts(with_cookies=True)
            with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore[arg-type]
                return dict(ydl.extract_info(url, download=False) or {})
        except Exception as e:
            logger.warning(f"yt-dlp (with cookies) failed for {url}: {e}")

        # Attempt 2: without cookies
        try:
            opts = _build_ydl_opts(with_cookies=False)
            with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore[arg-type]
                return dict(ydl.extract_info(url, download=False) or {})
        except Exception as e2:
            logger.error(f"yt-dlp (no cookies) also failed for {url}: {e2}")
            raise RuntimeError(
                f"Could not fetch data from URL: {url}. "
                "For Instagram/TikTok, export cookies.txt from your browser and place it in the backend/ directory."
            )

    def ingest(self, url: str) -> Dict[str, Any]:
        logger.info(f"Ingesting URL: {url}")

        info = self._fetch_info(url)
        if not info:
            raise RuntimeError(f"No metadata returned for: {url}")

        video_id: str = info.get('id', 'unknown_id')
        title: str = info.get('title') or 'Unknown Video'
        description: str = info.get('description') or title
        platform: str = info.get('extractor', 'unknown').split(':')[0].lower()

        # ---------------------------------------------------------------
        # Creator / uploader name
        # ---------------------------------------------------------------
        creator: str = (
            info.get('channel') or
            info.get('uploader') or
            info.get('creator') or
            'Unknown Creator'
        )

        # ---------------------------------------------------------------
        # Follower / subscriber count
        # Note: Instagram does not expose follower counts publicly via yt-dlp.
        # YouTube returns channel_follower_count for most channels.
        # ---------------------------------------------------------------
        raw_followers = (
            info.get('channel_follower_count') or
            info.get('uploader_follower_count') or
            info.get('subscriber_count')
        )
        follower_count: int = int(raw_followers) if raw_followers is not None else 0

        # ---------------------------------------------------------------
        # Hashtags — yt-dlp returns these in the 'tags' list
        # ---------------------------------------------------------------
        raw_tags = info.get('tags') or []
        hashtags: List[str] = [f"#{t.replace(' ', '')}" for t in raw_tags[:10] if t]

        # ---------------------------------------------------------------
        # Upload date — yt-dlp returns YYYYMMDD string
        # ---------------------------------------------------------------
        raw_date = info.get('upload_date')
        if raw_date and isinstance(raw_date, str) and len(raw_date) == 8:
            # Format YYYYMMDD → YYYY-MM-DD
            upload_date: str = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
        else:
            # Try unix timestamp fallback (some extractors return this)
            raw_ts = info.get('timestamp')
            if raw_ts:
                from datetime import datetime, timezone
                upload_date = datetime.fromtimestamp(float(raw_ts), tz=timezone.utc).strftime('%Y-%m-%d')
            else:
                upload_date = 'Unknown'

        # ---------------------------------------------------------------
        # Thumbnail URL — prefer the highest-resolution available
        # ---------------------------------------------------------------
        thumbnail_url: str = info.get('thumbnail') or ''
        thumbnails = info.get('thumbnails') or []
        if thumbnails:
            # yt-dlp lists thumbnails from low → high resolution
            best = thumbnails[-1].get('url', '')
            if best:
                thumbnail_url = best

        # ---------------------------------------------------------------
        # View / like / comment / duration counts
        # ---------------------------------------------------------------
        # View count — Instagram often omits this; try multiple keys
        raw_views = (
            info.get('view_count') or
            info.get('play_count') or
            info.get('video_view_count')
        )
        views: int = int(raw_views) if raw_views is not None else 0
        raw_likes = info.get('like_count')
        likes: int = int(raw_likes) if raw_likes is not None else 0
        raw_comments = info.get('comment_count')
        comments: int = int(raw_comments) if raw_comments is not None else 0
        raw_duration = info.get('duration')
        duration: int = int(raw_duration) if raw_duration is not None else 0

        # Estimate views for Instagram if missing (avg like rate ~5%)
        is_estimated_views = False
        if views == 0 and likes > 0:
            views = likes * 20
            is_estimated_views = True
            logger.info(f"Estimated views for {video_id}: {views} (based on {likes} likes)")

        engagement_rate = round(((likes + comments) / views) * 100, 2) if views > 0 else 0.0

        # ---------------------------------------------------------------
        # Transcript
        # ---------------------------------------------------------------
        transcript_data: List[Dict[str, Any]] = []
        whisper_stubbed = False
        asr_method: str = "none"
        error_message = None

        is_youtube = "youtube" in platform or "youtu.be" in url or "youtube.com" in url
        if is_youtube:
            try:
                transcript_data = _extract_yt_transcript(video_id)
                asr_method = "youtube_captions"
            except Exception as e:
                logger.warning(f"Transcript fetch failed for {video_id}: {e}")
                whisper_stubbed = True
                asr_method = "description"
                error_message = str(e)
        else:
            # For Instagram / TikTok: run the ASR cascade.
            # Downloads audio → Whisper API → Gemini Audio → description fallback.
            logger.info(f"Non-YouTube platform '{platform}' — running ASR cascade…")
            transcript_data, asr_method = _asr_transcribe(url)

            if asr_method == "description":
                # ASR cascade failed; use description pseudo-transcript as last resort.
                whisper_stubbed = True
                error_message = "ASR unavailable — using post caption as transcript context."
                transcript_data = _description_to_transcript(description, title)
            else:
                whisper_stubbed = False
                error_message = None
                logger.info(
                    f"Real ASR transcript obtained via '{asr_method}' "
                    f"({len(transcript_data)} segments) for video {video_id}."
                )

        # Final safety net — should never be needed after the cascade above
        if not transcript_data:
            transcript_data = [
                {"text": title, "start": 0.0, "duration": 5.0},
                {"text": description[:300], "start": 5.0, "duration": 10.0},
            ]

        return {
            "video_id": video_id,
            "platform": platform,
            "title": title,
            "creator": creator,
            "follower_count": follower_count,
            "hashtags": hashtags,
            "upload_date": upload_date,
            "thumbnail_url": thumbnail_url,
            "metrics": {
                "views": views,
                "likes": likes,
                "comments": comments,
                "duration": duration,
            },
            "engagement_rate": engagement_rate,
            "is_estimated_views": is_estimated_views,
            "transcript": transcript_data,
            "whisper_stubbed": whisper_stubbed,
            "asr_method": asr_method,
            "error_message": error_message,
        }


def get_ingestor_for_url(url: str) -> BaseIngestor:
    return RealMediaIngestor()
