from datetime import datetime, timedelta, timezone

import pandas as pd

from app.db.models import Investor, Recommendation
from app.llm.base import LLMClient
from app.llm.router import LLMRouter
from app.schemas.self_assessment import ReflectionOutput

CANNED_REFLECTION = ReflectionOutput(
    contributing_factors="Bond yields rose faster than assumed.",
    assumptions_held=False,
    reflection_summary="Underperformed the 6% assumption over the period.",
)


class FakeClient(LLMClient):
    name = "fake"

    def generate(self, prompt, schema):
        return CANNED_REFLECTION


class EmptyHistoryTicker:
    def history(self, **kwargs):
        return pd.DataFrame()


def _seed_investor_and_recommendation(db_session):
    investor = Investor(email="selfassess@example.com", hashed_password="x")
    db_session.add(investor)
    db_session.flush()

    recommendation = Recommendation(
        investor_id=investor.id,
        status="pending",
        payload={
            "what": "Shift to 70/30",
            "why": "growth focus",
            "expected_behavior": "grows over time",
            "goal_probability": 0.8,
            "risks": ["market risk"],
            "suggested_instruments": [],
        },
        generated_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=45),
    )
    db_session.add(recommendation)
    db_session.commit()
    return investor, recommendation


def test_trigger_evaluation_creates_evaluation_and_lists_it(
    client, db_session, monkeypatch, tmp_path, auth_headers
):
    investor, recommendation = _seed_investor_and_recommendation(db_session)
    headers = auth_headers(investor.id)

    import app.services.chroma_client as chroma_client_module

    monkeypatch.setattr(chroma_client_module.settings, "chroma_persist_dir", str(tmp_path))
    monkeypatch.setattr(chroma_client_module, "_client", None)
    monkeypatch.setattr(
        "app.agents.self_assessment.nodes.get_router", lambda: LLMRouter([FakeClient()])
    )
    monkeypatch.setattr("app.services.deviation.yf.Ticker", lambda ticker: EmptyHistoryTicker())

    response = client.post(
        f"/investors/{investor.id}/recommendations/{recommendation.id}/evaluations/", headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["recommendation_id"] == recommendation.id
    assert body["assumptions_held"] is False
    assert body["contributing_factors"] == CANNED_REFLECTION.contributing_factors

    list_response = client.get(
        f"/investors/{investor.id}/recommendations/{recommendation.id}/evaluations/", headers=headers
    )
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    similar = chroma_client_module.query_similar_reflections("growth focus")
    assert len(similar) == 1
    assert similar[0]["metadata"]["recommendation_id"] == recommendation.id


def test_trigger_evaluation_404_for_unknown_recommendation(client, db_session, auth_headers):
    investor = Investor(email="noreco@example.com", hashed_password="x")
    db_session.add(investor)
    db_session.commit()

    response = client.post(
        f"/investors/{investor.id}/recommendations/999/evaluations/", headers=auth_headers(investor.id)
    )
    assert response.status_code == 404
