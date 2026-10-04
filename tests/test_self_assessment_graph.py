from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.agents.self_assessment.graph import self_assessment_graph
from app.llm.base import LLMClient
from app.llm.router import LLMRouter
from app.schemas.self_assessment import ReflectionOutput

CANNED_REFLECTION = ReflectionOutput(
    contributing_factors="Rates rose faster than assumed.",
    assumptions_held=False,
    reflection_summary="Underperformed the 6% assumption.",
)


class FakeClient(LLMClient):
    name = "fake"

    def generate(self, prompt, schema):
        return CANNED_REFLECTION


class EmptyHistoryTicker:
    def history(self, **kwargs):
        import pandas as pd

        return pd.DataFrame()


def test_self_assessment_graph_end_to_end(monkeypatch):
    monkeypatch.setattr(
        "app.agents.self_assessment.nodes.get_router", lambda: LLMRouter([FakeClient()])
    )
    monkeypatch.setattr(
        "app.agents.self_assessment.nodes.chroma_client.query_similar_reflections",
        lambda query_text, n_results=3: [],
    )

    generated_at = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
    state = {
        "recommendation_payload": {
            "what": "Shift to 70/30",
            "why": "growth focus",
            "expected_behavior": "grows over time",
            "goal_probability": 0.8,
            "risks": ["market risk"],
            "suggested_instruments": [],
        },
        "generated_at": generated_at,
    }

    with patch("app.services.deviation.yf.Ticker", return_value=EmptyHistoryTicker()):
        result = self_assessment_graph.invoke(state)

    assert result["deviation"]["elapsed_days"] == 45
    assert result["contributing_factors"] == CANNED_REFLECTION.contributing_factors
    assert result["assumptions_held"] is False
    assert result["reflection_summary"] == CANNED_REFLECTION.reflection_summary
    assert result["llm_provider"] == "fake"
