from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Goal, Investor
from app.db.session import get_db
from app.schemas.goal import GoalCreate, GoalRead, GoalAnalysis
from app.services import goal_math

router = APIRouter(prefix="/investors/{investor_id}/goals", tags=["goals"])

CADENCE_PERIODS_PER_YEAR = {
    "monthly": 12,
    "quarterly": 4,
    "annually": 1,
}
DEFAULT_ASSUMED_RETURN = 0.06


@router.post("/", response_model=GoalRead)
def create_goal(investor_id: int, payload: GoalCreate, db: Session = Depends(get_db)):
    if db.get(Investor, investor_id) is None:
        raise HTTPException(status_code=404, detail="Investor not found")

    goal = Goal(investor_id=investor_id, **payload.model_dump())
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


@router.get("/", response_model=list[GoalRead])
def list_goals(investor_id: int, db: Session = Depends(get_db)):
    return db.query(Goal).filter(Goal.investor_id == investor_id).all()


@router.get("/{goal_id}/analysis", response_model=GoalAnalysis)
def analyze_goal(
    investor_id: int,
    goal_id: int,
    assumed_annual_return: float = DEFAULT_ASSUMED_RETURN,
    db: Session = Depends(get_db),
):
    goal = db.query(Goal).filter(Goal.investor_id == investor_id, Goal.id == goal_id).first()
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    if not goal.contribution_cadence or goal.contribution_amount is None:
        raise HTTPException(
            status_code=400,
            detail="Goal must have contribution_cadence and contribution_amount set to analyze",
        )

    periods_per_year = CADENCE_PERIODS_PER_YEAR.get(goal.contribution_cadence.lower())
    if periods_per_year is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown contribution_cadence '{goal.contribution_cadence}'. "
            f"Expected one of {list(CADENCE_PERIODS_PER_YEAR)}",
        )

    years = (goal.target_date - datetime.now(timezone.utc).replace(tzinfo=None)).days / 365.25
    if years <= 0:
        raise HTTPException(status_code=400, detail="target_date must be in the future")

    required_return = goal_math.required_annual_return(
        target_amount=goal.target_amount,
        current_amount=goal.current_amount,
        years=years,
        contribution_per_period=goal.contribution_amount,
        periods_per_year=periods_per_year,
    )
    projected_value = goal_math.project_future_value(
        current_amount=goal.current_amount,
        contribution_per_period=goal.contribution_amount,
        annual_return=assumed_annual_return,
        years=years,
        periods_per_year=periods_per_year,
    )
    is_sufficient = goal_math.is_contribution_sufficient(
        target_amount=goal.target_amount,
        current_amount=goal.current_amount,
        years=years,
        contribution_per_period=goal.contribution_amount,
        periods_per_year=periods_per_year,
        assumed_return=assumed_annual_return,
    )

    return GoalAnalysis(
        required_annual_return=required_return,
        is_sufficient=is_sufficient,
        projected_value=projected_value,
        assumed_annual_return=assumed_annual_return,
    )
