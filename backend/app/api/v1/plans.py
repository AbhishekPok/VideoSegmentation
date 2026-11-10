from fastapi import APIRouter, Path, Response, status

from ...dependencies import PlanServiceDep
from ...schemas import PlanDetail, PlanIn, PlanSummary, ProgressIn

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("", response_model=list[PlanSummary])
def list_plans(plans: PlanServiceDep):
    return plans.list()


@router.post("", response_model=PlanDetail, status_code=status.HTTP_201_CREATED)
def create_plan(body: PlanIn, plans: PlanServiceDep):
    return plans.create(body)


@router.get("/{plan_id}", response_model=PlanDetail)
def get_plan(plan_id: int, plans: PlanServiceDep):
    return plans.get(plan_id)


@router.put("/{plan_id}", response_model=PlanDetail)
def update_plan(plan_id: int, body: PlanIn, plans: PlanServiceDep):
    return plans.update(plan_id, body)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(plan_id: int, plans: PlanServiceDep):
    plans.delete(plan_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{plan_id}/progress/{day_index}", response_model=list[int])
def set_progress(plan_id: int, body: ProgressIn, plans: PlanServiceDep, day_index: int = Path(ge=0, le=100_000)):
    """Mark one study day done or not done. Returns the plan's done day indexes."""
    return plans.set_progress(plan_id, day_index, body.done)


@router.delete("/{plan_id}/progress", status_code=status.HTTP_204_NO_CONTENT)
def clear_progress(plan_id: int, plans: PlanServiceDep):
    plans.clear_progress(plan_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
