import re
import os
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

logger = logging.getLogger(__name__)

COOKIES_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'cookies.txt')
COOKIES_FILE = os.path.normpath(COOKIES_FILE)


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
        error_message = None

        is_youtube = "youtube" in platform or "youtu.be" in url or "youtube.com" in url
        if is_youtube:
            try:
                transcript_data = _extract_yt_transcript(video_id)
            except Exception as e:
                logger.warning(f"Transcript fetch failed for {video_id}: {e}")
                whisper_stubbed = True
                error_message = str(e)
        else:
            # For Instagram/TikTok: use the post caption as context
            whisper_stubbed = True
            error_message = "Non-YouTube video — using post caption as transcript context."
            transcript_data = _description_to_transcript(description, title)

        # Final safety net
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
            "error_message": error_message,
        }


def get_ingestor_for_url(url: str) -> BaseIngestor:
    return RealMediaIngestor()
