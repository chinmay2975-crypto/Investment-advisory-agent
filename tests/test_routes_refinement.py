from datetime import datetime, timedelta, timezone

from app.db.models import Goal, Investor, InvestorProfile, Recommendation
from app.llm.base import LLMClient
from app.llm.router import LLMRouter
from app.schemas.recommendation import RecommendationOutput

FIRST_REFINED_OUTPUT = RecommendationOutput(
    what="Shift to a 60/40 stock/bond split using VTI and BND",
    target_allocation={"stocks": 60, "bonds": 40},
    suggested_instruments=["VTI", "BND"],
    why="Excludes NVIDIA per the investor's request",
    expected_behavior="Slightly less volatile than the prior allocation",
    goal_probability=0.8,
    risks=["Market downturn risk"],
)

SECOND_REFINED_OUTPUT = RecommendationOutput(
    what="Shift to a 50/50 stock/bond split using VTI and BND",
    target_allocation={"stocks": 50, "bonds": 50},
    suggested_instruments=["VTI", "BND"],
    why="Adds more bonds on top of the earlier NVIDIA exclusion",
    expected_behavior="Lower volatility than the first refinement",
    goal_probability=0.75,
    risks=["Lower expected growth"],
)


class SequencedFakeClient(LLMClient):
    name = "fake"

    def __init__(self, outputs):
        self._outputs = list(outputs)

    def generate(self, prompt, schema):
        return self._outputs.pop(0)


def _seed_investor_profile_goal_recommendation(db_session):
    investor = Investor(email="refine@example.com", hashed_password="x")
    db_session.add(investor)
    db_session.flush()

    profile = InvestorProfile(investor_id=investor.id, risk_cadence="Balanced", horizon_years=15)
    db_session.add(profile)

    goal = Goal(
        investor_id=investor.id,
        category="Retirement",
        target_amount=50000,
        current_amount=5000,
        target_date=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=365 * 15),
        contribution_cadence="monthly",
        contribution_amount=200,
    )
    db_session.add(goal)
    db_session.flush()

    recommendation = Recommendation(
        investor_id=investor.id,
        goal_id=goal.id,
        status="pending",
        payload={
            "what": "Shift to a 70/30 stock/bond split using VTI, BND and NVDA",
            "target_allocation": {"stocks": 70, "bonds": 30},
            "suggested_instruments": ["VTI", "BND", "NVDA"],
            "why": "Initial recommendation",
            "expected_behavior": "Grows with the market",
            "goal_probability": 0.82,
            "risks": ["Market downturn risk"],
        },
        llm_provider="fake",
    )
    db_session.add(recommendation)
    db_session.commit()

    return investor, goal, recommendation


def test_refine_endpoint_creates_new_recommendation_and_accumulates_constraints(
    client, db_session, monkeypatch, auth_headers
):
    investor, goal, recommendation = _seed_investor_profile_goal_recommendation(db_session)
    headers = auth_headers(investor.id)

    monkeypatch.setattr("app.api.routes_refinement.query_context", lambda *args, **kwargs: [])

    fake_router = LLMRouter([SequencedFakeClient([FIRST_REFINED_OUTPUT])])
    monkeypatch.setattr("app.agents.refinement.nodes.get_router", lambda: fake_router)

    response = client.post(
        f"/investors/{investor.id}/recommendations/{recommendation.id}/refine",
        json={"message": "remove NVIDIA"},
        headers=headers,
    )
    assert response.status_code == 200
    first_refined = response.json()
    assert first_refined["payload"]["what"] == FIRST_REFINED_OUTPUT.what
    assert first_refined["id"] != recommendation.id

    session_response = client.get(
        f"/investors/{investor.id}/recommendations/{recommendation.id}/refinement-session",
        headers=headers,
    )
    assert session_response.status_code == 200
    session_body = session_response.json()
    assert session_body["current_recommendation_id"] == first_refined["id"]
    assert session_body["active_constraints"]["exclusions"] == ["remove NVIDIA"]
    assert len(session_body["messages"]) == 1

    fake_router_2 = LLMRouter([SequencedFakeClient([SECOND_REFINED_OUTPUT])])
    monkeypatch.setattr("app.agents.refinement.nodes.get_router", lambda: fake_router_2)

    second_response = client.post(
        f"/investors/{investor.id}/recommendations/{first_refined['id']}/refine",
        json={"message": "more bonds"},
        headers=headers,
    )
    assert second_response.status_code == 200
    second_refined = second_response.json()

    session_response_2 = client.get(
        f"/investors/{investor.id}/recommendations/{first_refined['id']}/refinement-session",
        headers=headers,
    )
    session_body_2 = session_response_2.json()
    assert session_body_2["current_recommendation_id"] == second_refined["id"]
    assert session_body_2["active_constraints"]["exclusions"] == ["remove NVIDIA"]
    assert session_body_2["active_constraints"]["tilts"] == ["more bonds"]
    assert len(session_body_2["messages"]) == 2


def test_refine_endpoint_rejects_stale_recommendation_id(client, db_session, monkeypatch, auth_headers):
    investor, goal, recommendation = _seed_investor_profile_goal_recommendation(db_session)
    headers = auth_headers(investor.id)

    monkeypatch.setattr("app.api.routes_refinement.query_context", lambda *args, **kwargs: [])
    fake_router = LLMRouter([SequencedFakeClient([FIRST_REFINED_OUTPUT])])
    monkeypatch.setattr("app.agents.refinement.nodes.get_router", lambda: fake_router)

    first_response = client.post(
        f"/investors/{investor.id}/recommendations/{recommendation.id}/refine",
        json={"message": "remove NVIDIA"},
        headers=headers,
    )
    assert first_response.status_code == 200

    stale_response = client.post(
        f"/investors/{investor.id}/recommendations/{recommendation.id}/refine",
        json={"message": "more bonds"},
        headers=headers,
    )
    assert stale_response.status_code == 409
