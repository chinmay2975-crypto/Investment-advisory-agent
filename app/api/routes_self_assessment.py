from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Recommendation, RecommendationEvaluation
from app.db.session import get_db
from app.dependencies import require_self
from app.schemas.self_assessment import EvaluationRead
from app.services.self_assessment import run_self_assessment

router = APIRouter(
    prefix="/investors/{investor_id}/recommendations/{recommendation_id}/evaluations",
    tags=["self-assessment"],
    dependencies=[Depends(require_self)],
)


def _get_recommendation_or_404(investor_id: int, recommendation_id: int, db: Session) -> Recommendation:
    recommendation = (
        db.query(Recommendation)
        .filter(Recommendation.investor_id == investor_id, Recommendation.id == recommendation_id)
        .first()
    )
    if recommendation is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return recommendation


@router.post("/", response_model=EvaluationRead)
def trigger_evaluation(investor_id: int, recommendation_id: int, db: Session = Depends(get_db)):
    recommendation = _get_recommendation_or_404(investor_id, recommendation_id, db)
    return run_self_assessment(db, recommendation)


@router.get("/", response_model=list[EvaluationRead])
def list_evaluations(investor_id: int, recommendation_id: int, db: Session = Depends(get_db)):
    _get_recommendation_or_404(investor_id, recommendation_id, db)
    return (
        db.query(RecommendationEvaluation)
        .filter(RecommendationEvaluation.recommendation_id == recommendation_id)
        .all()
    )
