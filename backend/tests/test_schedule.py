"""Unit tests for the pure scheduling logic (no HTTP, no database)."""
from datetime import date

import pytest

from app.services.schedule_service import build_schedule, fmt, parse_chapters, parse_time, video_id
from app.services.youtube_service import iso_duration

AWS_SEC = 181758  # 50:29:18, shown on YouTube as 2:02:29:18
EVERY_DAY = 0b1111111


@pytest.mark.parametrize(
    "s,expected",
    [
        ("45", 45),
        ("1:30", 90),
        ("13:52:10", 49930),
        ("2:02:29:18", AWS_SEC),
        ("50:29:18", AWS_SEC),
        ("90 min", 5400),
        ("2 h", 7200),
        ("1.5 hours", 5400),
        ("", None),
        ("abc", None),
        ("1:", None),
        ("nan", None),
        ("1:2:3:4:5", None),
    ],
)
def test_parse_time(s, expected):
    assert parse_time(s) == expected


def test_fmt_hours_above_24():
    assert fmt(AWS_SEC) == "50:29:18"
    assert fmt(59.5) == "0:01:00"  # rounds half up like JS Math.round


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=c3Cn4xYfxJY",
        "https://www.youtube.com/watch?list=x&v=c3Cn4xYfxJY&t=10s",
        "https://youtu.be/c3Cn4xYfxJY?t=5",
        "https://www.youtube.com/live/c3Cn4xYfxJY",
        "https://www.youtube.com/embed/c3Cn4xYfxJY",
        "https://www.youtube.com/shorts/c3Cn4xYfxJY",
        "c3Cn4xYfxJY",
    ],
)
def test_video_id(url):
    assert video_id(url) == "c3Cn4xYfxJY"


def test_video_id_rejects_junk():
    assert video_id("https://example.com/") == ""
    assert video_id("") == ""


def test_iso_duration():
    assert iso_duration("P2DT2H29M18S") == AWS_SEC
    assert iso_duration("PT45M") == 2700
    assert iso_duration("garbage") == 0


def test_real_description_skips_the_two_mistyped_chapters(aws_description):
    pc = parse_chapters(aws_description, AWS_SEC)
    assert pc.skipped == ["19:33:29 DocumentDB", "21:10:04 Amazon Keyspaces"]
    assert len(pc.chapters) == 80
    assert pc.beyond is None


def test_chapter_beyond_length_is_reported():
    pc = parse_chapters("0:00 Intro\n1:00:00 Part 2", 1800)
    assert pc.beyond == 3600
    assert [c.title for c in pc.chapters] == ["Intro"]


@pytest.mark.parametrize("speed,sessions", [(1.0, 51), (1.5, 34)])
def test_session_counts_match_handoff_checklist(speed, sessions):
    s = build_schedule(AWS_SEC, "", 60, speed, date(2026, 11, 10), True, EVERY_DAY)
    assert len(s["sessions"]) == sessions
    assert s["sessions"][0]["start_sec"] == 0
    assert s["sessions"][-1]["end_sec"] == AWS_SEC


def test_sessions_are_contiguous_and_snap_to_chapters(aws_description):
    s = build_schedule(AWS_SEC, aws_description, 60, 1.0, date(2026, 11, 10), True, EVERY_DAY)
    sess = s["sessions"]
    for a, b in zip(sess, sess[1:]):
        assert a["end_sec"] == b["start_sec"]
    chapter_times = {c.t for c in parse_chapters(aws_description, AWS_SEC).chapters}
    assert any(x["end_sec"] in chapter_times for x in sess[:-1])
    assert any("Skipped out-of-order timestamps" in w for w in s["warnings"])


def test_no_snap_gives_exact_hours():
    s = build_schedule(3 * 3600, "0:00 A\n0:50:00 B\n1:55:00 C", 60, 1.0, date(2026, 11, 10), False, EVERY_DAY)
    assert [x["end_sec"] for x in s["sessions"]] == [3600, 7200, 10800]


def test_short_tail_is_merged():
    # 2h05m at 60 min/day: the 5 min tail is < min(15 min, 25% of 60) so day 2 absorbs it
    s = build_schedule(2 * 3600 + 300, "", 60, 1.0, date(2026, 11, 10), False, EVERY_DAY)
    assert len(s["sessions"]) == 2
    assert s["sessions"][-1]["end_sec"] == 2 * 3600 + 300


def test_dates_skip_unselected_weekdays():
    # 2026-11-10 is a Tuesday. Study only Mon (1) and Wed (3).
    mask = (1 << 1) | (1 << 3)
    s = build_schedule(4 * 3600, "", 60, 1.0, date(2026, 11, 10), False, mask)
    assert [x["date"] for x in s["sessions"]] == ["2026-11-11", "2026-11-16", "2026-11-18", "2026-11-23"]


def test_continued_chapter_label():
    s = build_schedule(2 * 3600, "0:00 Long chapter", 60, 1.0, date(2026, 11, 10), False, EVERY_DAY)
    assert s["sessions"][1]["continues"] == "Long chapter"
    assert s["sessions"][0]["continues"] is None
