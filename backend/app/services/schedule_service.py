"""Scheduling logic: split one long video into daily study sessions.

Pure functions, no database or HTTP. Ported from the original single-file page
(parseTime, fmt, videoId, parseChapters, build) so behaviour stays the same.
"""
import math
import re
from dataclasses import dataclass
from datetime import date, timedelta

MAX_DURATION_SEC = 10 * 86400  # 10 days of video; keeps the session count bounded
SPEEDS = (1.0, 1.25, 1.5, 1.75, 2.0)
ALL_DAYS = 0b1111111

_MIN_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*(?:m|min|mins|minutes)$", re.I)
_HOUR_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*(?:h|hr|hrs|hours)$", re.I)
_PART_RE = re.compile(r"^\d+(?:\.\d+)?$")
_VIDEO_ID_RE = re.compile(r"(?:v=|youtu\.be/|/live/|/embed/|/shorts/)([A-Za-z0-9_-]{11})")
_BARE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_CHAPTER_TS_RE = re.compile(r"(\d{1,3}:\d{2}(?::\d{2})?)")
_TITLE_LEAD_RE = re.compile(r"^[\s\-–—:|.)\]]+")
_TITLE_TAIL_RE = re.compile(r"[\s\-–—:|]+$")


def parse_time(s: str) -> float | None:
    """Accepts ss, mm:ss, hh:mm:ss, d:hh:mm:ss (YouTube's 24h+ format), '90 min', '2 h'."""
    s = str(s).strip()
    if not s:
        return None
    if m := _MIN_RE.match(s):
        return float(m[1]) * 60
    if m := _HOUR_RE.match(s):
        return float(m[1]) * 3600
    parts = s.split(":")
    if len(parts) > 4 or not all(_PART_RE.match(p) for p in parts):
        return None
    nums = [float(p) for p in parts]
    if len(nums) == 4:
        return nums[0] * 86400 + nums[1] * 3600 + nums[2] * 60 + nums[3]
    total = 0.0
    for n in nums:
        total = total * 60 + n
    return total


def fmt(sec: float) -> str:
    """h:mm:ss, hours may exceed 24 (e.g. 50:29:18)."""
    sec = int(math.floor(sec + 0.5))
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def human(sec: float) -> str:
    m = int(math.floor(sec / 60 + 0.5))
    return f"{m // 60}h {m % 60}m" if m // 60 else f"{m}m"


def video_id(url: str) -> str:
    if not url:
        return ""
    if m := _VIDEO_ID_RE.search(url):
        return m[1]
    return url.strip() if _BARE_ID_RE.match(url.strip()) else ""


@dataclass
class Chapter:
    t: float
    title: str


@dataclass
class ParsedChapters:
    chapters: list[Chapter]
    skipped: list[str]  # out-of-order lines, as written
    beyond: float | None  # first chapter time past the total length


def parse_chapters(txt: str, dur: float) -> ParsedChapters:
    """Keeps description order; skips timestamps that do not increase."""
    chapters: list[Chapter] = []
    skipped: list[str] = []
    last = -1.0
    beyond = None
    for line in txt.splitlines():
        m = _CHAPTER_TS_RE.search(line)
        if not m:
            continue
        t = parse_time(m[1])
        if t is None:
            continue
        title = line.replace(m[1], "", 1)
        title = _TITLE_TAIL_RE.sub("", _TITLE_LEAD_RE.sub("", title)).strip() or "Chapter"
        if t <= last:
            skipped.append(f"{m[1]} {title}")
            continue
        if t > dur:
            if beyond is None:
                beyond = t
            continue
        chapters.append(Chapter(t, title))
        last = t
    return ParsedChapters(chapters, skipped, beyond)


def chapter_lines(description: str) -> list[str]:
    """Lines of a video description that look like chapter timestamps."""
    return [ln for ln in description.splitlines() if re.search(r"\d{1,3}:\d{2}", ln)]


def js_weekday(d: date) -> int:
    """0=Sunday ... 6=Saturday (matches JavaScript Date.getDay())."""
    return (d.weekday() + 1) % 7


def weekdays_to_mask(days: list[int]) -> int:
    mask = 0
    for d in days:
        mask |= 1 << d
    return mask


def mask_to_weekdays(mask: int) -> list[int]:
    return [d for d in range(7) if mask & (1 << d)]


def build_schedule(
    duration_sec: float,
    chapters_text: str,
    minutes_per_day: int,
    speed: float,
    start: date,
    snap_to_chapters: bool,
    weekday_mask: int,
) -> dict:
    dur = float(duration_sec)
    chunk = minutes_per_day * 60 * speed
    pc = parse_chapters(chapters_text, dur)
    chaps = pc.chapters

    warnings: list[str] = []
    if pc.beyond is not None:
        warnings.append(
            f"Total length ({fmt(dur)}) is shorter than a chapter at {fmt(pc.beyond)}. "
            "Check the length on YouTube."
        )
    if pc.skipped:
        warnings.append("Skipped out-of-order timestamps: " + ", ".join(pc.skipped))

    # Snap each session end to the nearest chapter within ±20% of the target;
    # merge a short tail (< min(25% of a session, 15 min)) into the last day.
    tol = chunk * 0.2
    min_tail = min(chunk * 0.25, 15 * 60)
    spans: list[tuple[float, float]] = []
    cur = 0.0
    while cur < dur - 1:
        end = min(cur + chunk, dur)
        if snap_to_chapters and chaps and end < dur:
            best = None
            for c in chaps:
                if c.t > cur + chunk * 0.5 and abs(c.t - end) <= tol and (
                    best is None or abs(c.t - end) < abs(best - end)
                ):
                    best = c.t
            if best is not None:
                end = best
        if dur - end < min_tail:
            end = dur
        spans.append((cur, end))
        cur = end

    mask = weekday_mask & ALL_DAYS or ALL_DAYS
    d = start
    sessions = []
    for i, (s, e) in enumerate(spans):
        guard = 0
        while not mask & (1 << js_weekday(d)) and guard < 7:
            d += timedelta(days=1)
            guard += 1
        inside = [c for c in chaps if s <= c.t < e]
        before = [c for c in chaps if c.t < s]
        continues = before[-1].title if before and (not inside or inside[0].t > s) else None
        sessions.append(
            {
                "index": i,
                "date": d.isoformat(),
                "start_sec": s,
                "end_sec": e,
                "start": fmt(s),
                "end": fmt(e),
                "watch_sec": (e - s) / speed,
                "watch": human((e - s) / speed),
                "continues": continues,
                "chapters": [{"t": c.t, "time": fmt(c.t), "title": c.title} for c in inside],
            }
        )
        d += timedelta(days=1)

    return {
        "duration_sec": dur,
        "duration": fmt(dur),
        "total_watch": human(dur / speed),
        "chapter_count": len(chaps),
        "skipped": pc.skipped,
        "warnings": warnings,
        "sessions": sessions,
    }
