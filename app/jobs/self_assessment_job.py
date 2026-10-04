from app.config import settings
from app.db.session import SessionLocal
from app.services.self_assessment import find_eligible_recommendations, run_self_assessment


def run_self_assessment_batch() -> int:
    """Governed batch evaluation, run periodically by APScheduler. Evaluates recommendations
    old enough to have a measurable outcome and logs the reflection to `recommendation_evaluations`
    for human review — never feeds back into the Recommendation Engine automatically.
    """
    db = SessionLocal()
    try:
        recommendations = find_eligible_recommendations(db, settings.self_assessment_horizon_days)
        for recommendation in recommendations:
            run_self_assessment(db, recommendation)
        return len(recommendations)
    finally:
        db.close()
