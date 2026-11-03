import json

import pytest

from app.db.models import Holding, Investor, InvestorProfile, Recommendation
from app.llm.base import LLMClient
from app.llm.router import LLMRouter
from app.schemas.recommendation import RecommendationOutput
from tests import market_fakes

CANNED = RecommendationOutput(
    what="Hold a 60/40 mix using Nifty 50 and Indian gilt funds",
    target_allocation={"stocks": 60, "bonds": 40},
    suggested_instruments=["NIFTYBEES.NS", "GILT5YBEES.NS"],
    why="Balances growth with the investor's risk cadence",
    expected_behavior="Moderate volatility",
    goal_probability=0.7,
    risks=["Equity drawdowns"],
)


class CapturingClient(LLMClient):
    name = "fake"

    def __init__(self):
        self.prompts = []

    def generate(self, prompt, schema):
        self.prompts.append(prompt)
        return CANNED


def parse_sse(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


@pytest.fixture
def llm(monkeypatch):
    market_fakes.install(monkeypatch)
    client = CapturingClient()
    monkeypatch.setattr("app.agents.advice.nodes.get_router", lambda: LLMRouter([client]))
    monkeypatch.setattr("app.agents.advice.nodes.query_context", lambda *a, **k: [])
    return client


def _investor_with_profile(db_session, country=None):
    investor = Investor(email="advice@example.com", hashed_password="x")
    db_session.add(investor)
    db_session.flush()
    db_session.add(InvestorProfile(investor_id=investor.id, risk_cadence="Balanced", horizon_years=10, country=country))
    db_session.commit()
    return investor


def test_stream_uses_saved_holdings_and_emits_stages_sections_and_done(client, db_session, auth_headers, llm):
    investor = _investor_with_profile(db_session)
    db_session.add(Holding(investor_id=investor.id, ticker="RELIANCE.NS", quantity=10, source="manual"))
    db_session.commit()

    response = client.post("/advice/stream", json={}, headers=auth_headers(investor.id))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response.text)
    names = [name for name, _ in events]

    assert names[0] == "stage" and events[0][1]["status"] == "started"
    completed = [d["stage"] for n, d in events if n == "stage" and d["status"] == "completed"]
    assert completed == ["analyze_portfolio", "load_country_context", "retrieve_market_context", "generate_advice"]
    context = next(d for n, d in events if n == "context")
    assert (context["country"], context["currency"], context["source"]) == ("IN", "INR", "inferred")
    section_keys = [d["key"] for n, d in events if n == "section"]
    assert section_keys[0] == "what" and section_keys[-1] == "disclaimer"
    assert names[-1] == "done"

    saved = db_session.get(Recommendation, events[-1][1]["recommendation_id"])
    assert saved.payload["what"] == CANNED.what
    # country context flows into the prompt via state
    assert "Nifty 50" in llm.prompts[0] and "INR" in llm.prompts[0]


def test_stream_with_country_and_no_holdings(client, db_session, auth_headers, llm):
    investor = _investor_with_profile(db_session)
    response = client.post("/advice/stream", json={"holdings": [], "country": "UK"}, headers=auth_headers(investor.id))
    events = parse_sse(response.text)
    context = next(d for n, d in events if n == "context")
    assert (context["country"], context["source"]) == ("GB", "user_selected")
    assert "FTSE 100" in llm.prompts[0]
    assert "No current holdings provided" in llm.prompts[0]


def test_profile_country_used_when_request_omits_it(client, db_session, auth_headers, llm):
    investor = _investor_with_profile(db_session, country="GB")
    db_session.add(Holding(investor_id=investor.id, ticker="AAPL", quantity=1, source="manual"))
    db_session.commit()
    events = parse_sse(client.post("/advice/stream", json={}, headers=auth_headers(investor.id)).text)
    assert next(d for n, d in events if n == "context")["country"] == "GB"


def test_llm_failure_becomes_error_event(client, db_session, auth_headers, llm, monkeypatch):
    class Failing(LLMClient):
        name = "failing"

        def generate(self, prompt, schema):
            raise RuntimeError("model unavailable")

    monkeypatch.setattr("app.agents.advice.nodes.get_router", lambda: LLMRouter([Failing()]))
    investor = _investor_with_profile(db_session)
    events = parse_sse(
        client.post("/advice/stream", json={"holdings": [], "country": "IN"}, headers=auth_headers(investor.id)).text
    )
    assert events[-1] == ("error", {"message": "model unavailable"})


def test_requires_profile(client, db_session, auth_headers, llm):
    investor = Investor(email="noprofile-advice@example.com", hashed_password="x")
    db_session.add(investor)
    db_session.commit()
    response = client.post("/advice/stream", json={"country": "IN"}, headers=auth_headers(investor.id))
    assert response.status_code == 400


def test_no_holdings_and_no_country_is_400(client, db_session, auth_headers, llm):
    investor = _investor_with_profile(db_session)
    response = client.post("/advice/stream", json={}, headers=auth_headers(investor.id))
    assert response.status_code == 400
