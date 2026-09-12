from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Goal, Investor
from app.db.session import get_db
from app.schemas.goal import GoalCreate, GoalRead, GoalAnalysis
from app.services.goal_analysis import analyze_goal as compute_goal_analysis, GoalAnalysisError, DEFAULT_ASSUMED_RETURN

router = APIRouter(prefix="/investors/{investor_id}/goals", tags=["goals"])


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

    try:
        analysis = compute_goal_analysis(goal, assumed_annual_return)
    except GoalAnalysisError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return GoalAnalysis(**analysis)
