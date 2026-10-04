from app.agents.scenario.nodes import aggressive_node, balanced_node, conservative_node
from app.llm.base import LLMClient
from app.llm.router import LLMRouter
from app.schemas.recommendation import RecommendationOutput

CANNED_OUTPUT = RecommendationOutput(
    what="Some allocation",
    target_allocation={"stocks": 50, "bonds": 50},
    suggested_instruments=["VTI", "BND"],
    why="Because",
    expected_behavior="Steady",
    goal_probability=0.7,
    risks=["Market risk"],
)


class FakeClient(LLMClient):
    name = "fake"

    def generate(self, prompt, schema):
        assert schema is RecommendationOutput
        return CANNED_OUTPUT


def _base_state():
    return {
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


def test_conservative_node_uses_conservative_allocation_and_risk_cadence(monkeypatch):
    captured_prompts = []

    class CapturingClient(LLMClient):
        name = "fake"

        def generate(self, prompt, schema):
            captured_prompts.append(prompt)
            return CANNED_OUTPUT

    monkeypatch.setattr(
        "app.agents.scenario.nodes.get_router", lambda: LLMRouter([CapturingClient()])
    )

    result = conservative_node(_base_state())

    assert result["conservative"] == CANNED_OUTPUT.model_dump()
    assert result["conservative_provider"] == "fake"
    assert "Conservative" in captured_prompts[0]


def test_balanced_and_aggressive_nodes_return_output_and_provider(monkeypatch):
    monkeypatch.setattr(
        "app.agents.scenario.nodes.get_router", lambda: LLMRouter([FakeClient()])
    )

    balanced_result = balanced_node(_base_state())
    aggressive_result = aggressive_node(_base_state())

    assert balanced_result["balanced"] == CANNED_OUTPUT.model_dump()
    assert balanced_result["balanced_provider"] == "fake"
    assert aggressive_result["aggressive"] == CANNED_OUTPUT.model_dump()
    assert aggressive_result["aggressive_provider"] == "fake"
