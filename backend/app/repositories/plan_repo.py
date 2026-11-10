from collections.abc import Sequence

from sqlalchemy import delete, func, select

from ..models import Plan, PlanProgress
from .base import BaseRepository


class PlanRepository(BaseRepository[Plan]):
    model = Plan

    def list_for_user(self, user_id: int) -> Sequence[Plan]:
        return self.db.scalars(select(Plan).where(Plan.user_id == user_id).order_by(Plan.updated_at.desc())).all()

    def count_for_user(self, user_id: int) -> int:
        return self.db.scalar(select(func.count()).select_from(Plan).where(Plan.user_id == user_id)) or 0

    def get_for_user(self, plan_id: int, user_id: int) -> Plan | None:
        return self.db.scalar(select(Plan).where(Plan.id == plan_id, Plan.user_id == user_id))

    # ---- progress ----
    def get_progress(self, plan_id: int, day_index: int) -> PlanProgress | None:
        return self.db.get(PlanProgress, (plan_id, day_index))

    def add_progress(self, plan_id: int, day_index: int) -> None:
        self.db.add(PlanProgress(plan_id=plan_id, day_index=day_index))
        self.db.flush()

    def clear_progress(self, plan_id: int) -> None:
        self.db.execute(delete(PlanProgress).where(PlanProgress.plan_id == plan_id))

    def done_days(self, plan_id: int) -> list[int]:
        return list(
            self.db.scalars(
                select(PlanProgress.day_index).where(PlanProgress.plan_id == plan_id).order_by(PlanProgress.day_index)
            )
        )
