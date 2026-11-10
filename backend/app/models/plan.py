from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, utcnow


class Plan(TimestampMixin, Base):
    """One study plan: a video split into daily sessions."""

    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    video_url: Mapped[str] = mapped_column(String(500), default="")
    duration_sec: Mapped[int] = mapped_column(Integer)
    chapters: Mapped[str] = mapped_column(Text, default="")
    minutes_per_day: Mapped[int] = mapped_column(SmallInteger)
    speed_pct: Mapped[int] = mapped_column(SmallInteger, default=100)  # 125 = 1.25x
    start_date: Mapped[date] = mapped_column(Date)
    snap_to_chapters: Mapped[bool] = mapped_column(Boolean, default=True)
    # Bitmask of study weekdays: bit d set for day d, where 0=Sunday ... 6=Saturday.
    weekdays: Mapped[int] = mapped_column(SmallInteger, default=0b1111111)

    progress: Mapped[list["PlanProgress"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, lazy="selectin"
    )

    @property
    def speed(self) -> float:
        return self.speed_pct / 100


class PlanProgress(Base):
    """One row per finished study day of a plan."""

    __tablename__ = "plan_progress"

    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), primary_key=True)
    day_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    done_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
