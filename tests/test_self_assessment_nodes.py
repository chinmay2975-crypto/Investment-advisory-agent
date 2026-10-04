from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.agents.self_assessment.nodes import build_reflection_prompt, evaluate_node, reflect_node, retrieve_similar_node
from app.llm.base import LLMClient
from app.llm.router import LLMRouter
from app.schemas.self_assessment import ReflectionOutput

CANNED_REFLECTION = ReflectionOutput(
    contributing_factors="Bond yields rose faster than assumed, pulling down the fixed-income sleeve.",
    assumptions_held=False,
    reflection_summary="Balanced allocation underperformed the 6% assumption over 60 days due to rate moves.",
)


class FakeClient(LLMClient):
    name = "fake"

    def generate(self, prompt, schema):
        assert schema is ReflectionOutput
        return CANNED_REFLECTION


def test_evaluate_node_computes_deviation():
    generated_at = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
    state = {
        "recommendation_payload": {"suggested_instruments": []},
        "generated_at": generated_at,
    }
    result = evaluate_node(state)
    assert result["deviation"]["elapsed_days"] == 45
    assert result["deviation"]["realized_return_pct"] == 0.0


def test_retrieve_similar_node_returns_chroma_results(monkeypatch):
    monkeypatch.setattr(
        "app.agents.self_assessment.nodes.chroma_client.query_similar_reflections",
        lambda query_text, n_results=3: [{"text": "prior case", "metadata": {}, "distance": 0.1}],
    )
    state = {"recommendation_payload": {"what": "Shift to 70/30", "why": "growth focus"}}
    result = retrieve_similar_node(state)
    assert result["similar_reflections"] == [{"text": "prior case", "metadata": {}, "distance": 0.1}]


def test_build_reflection_prompt_includes_deviation_and_precedent():
    prompt = build_reflection_prompt(
        payload={
            "what": "Shift to 70/30",
            "why": "growth focus",
            "expected_behavior": "grows over time",
            "goal_probability": 0.8,
            "risks": ["market risk"],
        },
        deviation={
            "elapsed_days": 45,
            "realized_return_pct": 1.0,
            "expected_return_pct": 3.0,
            "deviation_pct": -2.0,
            "per_instrument": {"VTI": 1.0},
        },
        similar_reflections=[{"text": "prior similar case", "metadata": {}, "distance": 0.2}],
    )
    assert "Shift to 70/30" in prompt
    assert "-2.00" in prompt
    assert "prior similar case" in prompt


def test_reflect_node_returns_structured_output_and_provider(monkeypatch):
    monkeypatch.setattr(
        "app.agents.self_assessment.nodes.get_router", lambda: LLMRouter([FakeClient()])
    )
    state = {
        "recommendation_payload": {
            "what": "Shift to 70/30",
            "why": "growth focus",
            "expected_behavior": "grows over time",
            "goal_probability": 0.8,
            "risks": ["market risk"],
        },
        "deviation": {
            "elapsed_days": 45,
            "realized_return_pct": 1.0,
            "expected_return_pct": 3.0,
            "deviation_pct": -2.0,
            "per_instrument": {"VTI": 1.0},
        },
        "similar_reflections": [],
    }
    result = reflect_node(state)
    assert result["contributing_factors"] == CANNED_REFLECTION.contributing_factors
    assert result["assumptions_held"] is False
    assert result["llm_provider"] == "fake"
