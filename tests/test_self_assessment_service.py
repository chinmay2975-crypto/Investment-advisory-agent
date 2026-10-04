from datetime import datetime, timedelta

from app.db.models import Investor, Recommendation, RecommendationEvaluation
from app.services.self_assessment import find_eligible_recommendations


def _seed_recommendation(db_session, generated_at, evaluated=False):
    investor = Investor(email=f"elig{generated_at.isoformat()}@example.com", hashed_password="x")
    db_session.add(investor)
    db_session.flush()

    recommendation = Recommendation(
        investor_id=investor.id,
        status="pending",
        payload={"what": "x", "suggested_instruments": []},
        generated_at=generated_at,
    )
    db_session.add(recommendation)
    db_session.flush()

    if evaluated:
        db_session.add(
            RecommendationEvaluation(recommendation_id=recommendation.id, deviation={}, assumptions_held=True)
        )
    db_session.commit()
    return recommendation


def test_find_eligible_recommendations_excludes_recent_and_already_evaluated(db_session):
    old_unevaluated = _seed_recommendation(db_session, datetime.utcnow() - timedelta(days=40))
    old_evaluated = _seed_recommendation(db_session, datetime.utcnow() - timedelta(days=40), evaluated=True)
    recent = _seed_recommendation(db_session, datetime.utcnow() - timedelta(days=5))

    eligible = find_eligible_recommendations(db_session, horizon_days=30)
    eligible_ids = {r.id for r in eligible}

    assert old_unevaluated.id in eligible_ids
    assert old_evaluated.id not in eligible_ids
    assert recent.id not in eligible_ids
