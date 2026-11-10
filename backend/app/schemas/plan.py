from datetime import date

from pydantic import BaseModel, Field, field_validator

from ..services.schedule_service import MAX_DURATION_SEC, SPEEDS, parse_time


class PlanIn(BaseModel):
    title: str = Field("Untitled plan", max_length=200)
    video_url: str = Field("", max_length=500)
    duration: str = Field(max_length=32, description="e.g. 50:29:18, 2:02:29:18 or 90 min")
    chapters: str = Field("", max_length=50_000)
    minutes_per_day: int = Field(60, ge=10, le=480)
    speed: float = 1.0
    start_date: date
    snap_to_chapters: bool = True
    weekdays: list[int] = Field(default_factory=lambda: list(range(7)), description="0=Sun ... 6=Sat")

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        return v.strip() or "Untitled plan"

    @field_validator("video_url")
    @classmethod
    def _url(cls, v: str) -> str:
        return v.strip()

    @field_validator("duration")
    @classmethod
    def _duration(cls, v: str) -> str:
        sec = parse_time(v)
        if not sec or sec <= 0:
            raise ValueError("Enter the total length like 13:52:10 or 90 min.")
        if sec > MAX_DURATION_SEC:
            raise ValueError("That length is longer than 10 days. Check the value.")
        return v.strip()

    @field_validator("speed")
    @classmethod
    def _speed(cls, v: float) -> float:
        if v not in SPEEDS:
            raise ValueError(f"Speed must be one of {', '.join(map(str, SPEEDS))}.")
        return v

    @field_validator("weekdays")
    @classmethod
    def _weekdays(cls, v: list[int]) -> list[int]:
        days = sorted(set(v))
        if not days or any(d < 0 or d > 6 for d in days):
            raise ValueError("Pick at least one study day (0=Sun ... 6=Sat).")
        return days

    @property
    def duration_sec(self) -> int:
        return int(round(parse_time(self.duration) or 0))


class PlanOut(BaseModel):
    id: int
    title: str
    video_url: str
    video_id: str
    duration: str
    duration_sec: int
    chapters: str
    minutes_per_day: int
    speed: float
    start_date: date
    snap_to_chapters: bool
    weekdays: list[int]


class ChapterOut(BaseModel):
    t: float
    time: str
    title: str


class SessionOut(BaseModel):
    index: int
    date: date
    start_sec: float
    end_sec: float
    start: str
    end: str
    watch_sec: float
    watch: str
    continues: str | None
    chapters: list[ChapterOut]


class ScheduleOut(BaseModel):
    duration_sec: float
    duration: str
    total_watch: str
    chapter_count: int
    skipped: list[str]
    warnings: list[str]
    sessions: list[SessionOut]


class PlanSummary(BaseModel):
    id: int
    title: str
    video_id: str
    duration: str
    sessions_total: int
    sessions_done: int


class PlanDetail(BaseModel):
    plan: PlanOut
    schedule: ScheduleOut
    done: list[int]


class ProgressIn(BaseModel):
    done: bool
