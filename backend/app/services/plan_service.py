"""Plan CRUD and progress, always scoped to one user."""
from sqlalchemy.orm import Session

from ..exceptions import BadRequestError, NotFoundError
from ..models import Plan, User
from ..repositories import PlanRepository
from ..schemas import PlanDetail, PlanIn, PlanOut, PlanSummary
from . import schedule_service as sched

MAX_PLANS_PER_USER = 200


def schedule_for(plan: Plan) -> dict:
    return sched.build_schedule(
        plan.duration_sec,
        plan.chapters,
        plan.minutes_per_day,
        plan.speed,
        plan.start_date,
        plan.snap_to_chapters,
        plan.weekdays,
    )


def to_out(plan: Plan) -> PlanOut:
    return PlanOut(
        id=plan.id,
        title=plan.title,
        video_url=plan.video_url,
        video_id=sched.video_id(plan.video_url),
        duration=sched.fmt(plan.duration_sec),
        duration_sec=plan.duration_sec,
        chapters=plan.chapters,
        minutes_per_day=plan.minutes_per_day,
        speed=plan.speed,
        start_date=plan.start_date,
        snap_to_chapters=plan.snap_to_chapters,
        weekdays=sched.mask_to_weekdays(plan.weekdays),
    )


def _apply(plan: Plan, body: PlanIn) -> None:
    plan.title = body.title
    plan.video_url = body.video_url
    plan.duration_sec = body.duration_sec
    plan.chapters = body.chapters
    plan.minutes_per_day = body.minutes_per_day
    plan.speed_pct = round(body.speed * 100)
    plan.start_date = body.start_date
    plan.snap_to_chapters = body.snap_to_chapters
    plan.weekdays = sched.weekdays_to_mask(body.weekdays)


class PlanService:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self.plans = PlanRepository(db)

    def _owned(self, plan_id: int) -> Plan:
        plan = self.plans.get_for_user(plan_id, self.user.id)
        if not plan:  # same answer for "missing" and "someone else's"
            raise NotFoundError("Plan not found")
        return plan

    def _detail(self, plan: Plan) -> PlanDetail:
        schedule = schedule_for(plan)
        n = len(schedule["sessions"])
        done = sorted(p.day_index for p in plan.progress if p.day_index < n)
        return PlanDetail(plan=to_out(plan), schedule=schedule, done=done)

    def list(self) -> list[PlanSummary]:
        out = []
        for p in self.plans.list_for_user(self.user.id):
            n = len(schedule_for(p)["sessions"])
            out.append(
                PlanSummary(
                    id=p.id,
                    title=p.title,
                    video_id=sched.video_id(p.video_url),
                    duration=sched.fmt(p.duration_sec),
                    sessions_total=n,
                    sessions_done=sum(1 for x in p.progress if x.day_index < n),
                )
            )
        return out

    def create(self, body: PlanIn) -> PlanDetail:
        if self.plans.count_for_user(self.user.id) >= MAX_PLANS_PER_USER:
            raise BadRequestError(f"You can have at most {MAX_PLANS_PER_USER} plans.")
        plan = Plan(user_id=self.user.id)
        _apply(plan, body)
        self.plans.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return self._detail(plan)

    def get(self, plan_id: int) -> PlanDetail:
        return self._detail(self._owned(plan_id))

    def update(self, plan_id: int, body: PlanIn) -> PlanDetail:
        plan = self._owned(plan_id)
        _apply(plan, body)
        self.db.commit()
        self.db.refresh(plan)
        return self._detail(plan)

    def delete(self, plan_id: int) -> None:
        self.plans.delete(self._owned(plan_id))
        self.db.commit()

    def set_progress(self, plan_id: int, day_index: int, done: bool) -> list[int]:
        """Mark one study day done or not done. Returns the plan's done day indexes."""
        plan = self._owned(plan_id)
        if day_index >= len(schedule_for(plan)["sessions"]):
            raise BadRequestError("No such day in this plan")
        row = self.plans.get_progress(plan.id, day_index)
        if done and not row:
            self.plans.add_progress(plan.id, day_index)
        elif not done and row:
            self.db.delete(row)
        self.db.commit()
        return self.plans.done_days(plan.id)

    def clear_progress(self, plan_id: int) -> None:
        plan = self._owned(plan_id)
        self.plans.clear_progress(plan.id)
        self.db.commit()
