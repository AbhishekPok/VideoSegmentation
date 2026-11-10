"""Server-side YouTube Data API v3 lookup. The API key never reaches the browser."""
import re
import threading
import time

import httpx

from ..config import settings
from ..exceptions import NotFoundError, UpstreamError
from ..schemas import VideoMeta
from .schedule_service import chapter_lines, fmt

API_URL = "https://www.googleapis.com/youtube/v3/videos"
NOT_CONFIGURED = "not_configured"
_ISO_RE = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$")
_CACHE_TTL = 3600
_cache: dict[str, tuple[float, VideoMeta]] = {}
_lock = threading.Lock()


def iso_duration(s: str) -> int:
    """'P2DT2H29M18S' -> 181758"""
    m = _ISO_RE.match(s or "")
    if not m:
        return 0
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


def is_configured() -> bool:
    return bool(settings.youtube_api_key)


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def get_video_meta(video_id: str) -> VideoMeta:
    """Length and chapter lines for one video.

    Cached in memory for an hour (videos.list costs 1 quota unit of 10,000/day).
    Raises NotFoundError('not_configured') when no key is set, so the frontend
    can fall back to reading the length from the YouTube player.
    """
    if not is_configured():
        raise NotFoundError(NOT_CONFIGURED)
    now = time.monotonic()
    with _lock:
        hit = _cache.get(video_id)
        if hit and now - hit[0] < _CACHE_TTL:
            return hit[1]
    try:
        r = httpx.get(
            API_URL,
            params={"part": "contentDetails,snippet", "id": video_id, "key": settings.youtube_api_key},
            timeout=8.0,
        )
    except httpx.HTTPError as e:
        raise UpstreamError(f"Couldn't reach YouTube ({type(e).__name__}).") from e
    try:
        data = r.json()
    except ValueError:
        data = {}
    if r.status_code != 200:
        msg = (data.get("error") or {}).get("message") or f"HTTP {r.status_code}"
        raise UpstreamError(f"YouTube API error: {msg}")
    items = data.get("items") or []
    if not items:
        raise NotFoundError("Video not found or private.")
    item = items[0]
    lines = chapter_lines((item.get("snippet") or {}).get("description") or "")
    has_chapters = len(lines) >= 2
    dur = iso_duration((item.get("contentDetails") or {}).get("duration", ""))
    meta = VideoMeta(
        video_id=video_id,
        duration_sec=dur,
        duration=fmt(dur),
        chapters="\n".join(lines) if has_chapters else "",
        chapter_count=len(lines) if has_chapters else 0,
    )
    with _lock:
        _cache[video_id] = (now, meta)
    return meta
