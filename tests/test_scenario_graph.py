from app.agents.scenario.graph import scenario_graph
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


def test_scenario_graph_produces_all_three_variants(monkeypatch):
    monkeypatch.setattr(
        "app.agents.scenario.nodes.get_router", lambda: LLMRouter([VariantAwareClient()])
    )

    state = {
        "profile": {"risk_cadence": "Balanced", "horizon_years": 15, "preferences": {}, "restrictions": {}},
        "goal": {
            "category": "Retirement",
            "target_amount": 50000,
            "current_amount": 5000,
            "target_date": "2041-01-01T00:00:00+00:00",
            "contribution_cadence": "monthly",
            "contribution_amount": 200,
        },
        "goal_analysis": None,
        "context_docs": [],
    }

    result = scenario_graph.invoke(state)

    assert result["conservative"]["what"] == "conservative pick"
    assert result["balanced"]["what"] == "balanced pick"
    assert result["aggressive"]["what"] == "aggressive pick"
    assert result["conservative_provider"] == "fake"
