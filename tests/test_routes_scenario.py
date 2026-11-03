from datetime import datetime, timedelta, timezone

from app.db.models import Goal, Investor, InvestorProfile
from app.llm.base import LLMClient
from app.llm.router import LLMRouter
from app.schemas.recommendation import RecommendationOutput


def _output_for(what: str) -> RecommendationOutput:
    return RecommendationOutput(
        what=what,
        target_allocation={"stocks": 50, "bonds": 50},
        suggested_instruments=["VTI", "BND"],
        why="Because",
        expected_behavior="Steady",
        goal_probability=0.7,
        risks=["Market risk"],
    )


class VariantAwareClient(LLMClient):
    name = "fake"

    def generate(self, prompt, schema):
        if "Conservative" in prompt:
            return _output_for("conservative pick")
        if "Aggressive" in prompt:
            return _output_for("aggressive pick")
        return _output_for("balanced pick")


def _seed_investor_profile_goal(db_session):
    investor = Investor(email="scenario@example.com", hashed_password="x")
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
    db_session.commit()

    return investor, goal


def test_create_scenario_run_returns_three_distinct_recommendations(
    client, db_session, monkeypatch, auth_headers
):
    investor, goal = _seed_investor_profile_goal(db_session)
    headers = auth_headers(investor.id)

    monkeypatch.setattr("app.api.routes_scenario.query_context", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        "app.agents.scenario.nodes.get_router", lambda: LLMRouter([VariantAwareClient()])
    )

    response = client.post(f"/investors/{investor.id}/goals/{goal.id}/scenarios/", headers=headers)
    assert response.status_code == 200
    body = response.json()

    assert body["conservative_recommendation"]["payload"]["what"] == "conservative pick"
    assert body["balanced_recommendation"]["payload"]["what"] == "balanced pick"
    assert body["aggressive_recommendation"]["payload"]["what"] == "aggressive pick"

    ids = {
        body["conservative_recommendation"]["id"],
        body["balanced_recommendation"]["id"],
        body["aggressive_recommendation"]["id"],
    }
    assert len(ids) == 3

    list_response = client.get(f"/investors/{investor.id}/goals/{goal.id}/scenarios/", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    get_response = client.get(
        f"/investors/{investor.id}/goals/{goal.id}/scenarios/{body['id']}", headers=headers
    )
    assert get_response.status_code == 200
    assert get_response.json()["id"] == body["id"]


class SameProbabilityClient(LLMClient):
    """Mimics the real bug: the LLM returns the same goal_probability for every risk level."""

    name = "fake"

    def generate(self, prompt, schema):
        stocks = 30 if "Conservative" in prompt else 90 if "Aggressive" in prompt else 60
        return _output_for("pick").model_copy(update={"target_allocation": {"stocks": stocks, "bonds": 100 - stocks}})


def test_scenario_probabilities_are_simulated_not_llm_guesses(client, db_session, monkeypatch, auth_headers):
    investor, goal = _seed_investor_profile_goal(db_session)
    monkeypatch.setattr("app.api.routes_scenario.query_context", lambda *a, **k: [])
    monkeypatch.setattr("app.agents.scenario.nodes.get_router", lambda: LLMRouter([SameProbabilityClient()]))

    body = client.post(f"/investors/{investor.id}/goals/{goal.id}/scenarios/", headers=auth_headers(investor.id)).json()
    payloads = [body[f"{v}_recommendation"]["payload"] for v in ("conservative", "balanced", "aggressive")]

    assert all(p["goal_probability_method"] == "monte_carlo" for p in payloads)
    assert all(p["llm_goal_probability"] == 0.7 for p in payloads)
    assert len({p["goal_probability"] for p in payloads}) == 3
    vols = [p["simulation"]["volatility"] for p in payloads]
    assert vols == sorted(vols)  # conservative < balanced < aggressive
