from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Goal, Investor
from app.db.session import get_db
from app.schemas.goal import GoalCreate, GoalRead

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
