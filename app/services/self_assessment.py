from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.self_assessment.graph import self_assessment_graph
from app.db.models import Recommendation, RecommendationEvaluation
from app.services import chroma_client


def find_eligible_recommendations(db: Session, horizon_days: int) -> list[Recommendation]:
    """Recommendations old enough to evaluate that haven't been evaluated yet."""
    cutoff = datetime.utcnow() - timedelta(days=horizon_days)
    already_evaluated = select(RecommendationEvaluation.recommendation_id)
    return (
        db.query(Recommendation)
        .filter(Recommendation.generated_at <= cutoff)
        .filter(~Recommendation.id.in_(already_evaluated))
        .all()
    )


def run_self_assessment(db: Session, recommendation: Recommendation) -> RecommendationEvaluation:
    state = {
        "recommendation_payload": recommendation.payload,
        "generated_at": recommendation.generated_at.isoformat(),
    }
    result = self_assessment_graph.invoke(state)

    evaluation = RecommendationEvaluation(
        recommendation_id=recommendation.id,
        deviation=result["deviation"],
        contributing_factors=result["contributing_factors"],
        assumptions_held=result["assumptions_held"],
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)

    chroma_client.ingest_reflection(
        evaluation_id=evaluation.id,
        recommendation_id=recommendation.id,
        text=(
            f"Recommendation: {recommendation.payload.get('what')}. "
            f"Rationale: {recommendation.payload.get('why')}. "
            f"Outcome: {result.get('reflection_summary', '')}"
        ),
        metadata={
            "assumptions_held": result["assumptions_held"],
            "deviation_pct": result["deviation"]["deviation_pct"],
            "evaluated_at": evaluation.evaluated_at.isoformat(),
        },
    )
    return evaluation
