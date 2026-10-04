from app.agents.refinement.graph import refinement_graph
from app.llm.base import LLMClient
from app.llm.router import LLMRouter
from app.schemas.recommendation import RecommendationOutput

CANNED_OUTPUT = RecommendationOutput(
    what="Shift to a 60/40 stock/bond split using VTI and BND",
    target_allocation={"stocks": 60, "bonds": 40},
    suggested_instruments=["VTI", "BND"],
    why="Honors the exclusion request while keeping the goal on track",
    expected_behavior="Slightly less volatile than the prior allocation",
    goal_probability=0.8,
    risks=["Market downturn risk"],
)


class FakeClient(LLMClient):
    name = "fake"

    def generate(self, prompt, schema):
        return CANNED_OUTPUT


def test_refinement_graph_merges_constraints_and_produces_recommendation(monkeypatch):
    monkeypatch.setattr(
        "app.agents.refinement.nodes.get_router", lambda: LLMRouter([FakeClient()])
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
        "default_allocation": {"stocks": 60, "bonds": 40},
        "context_docs": [],
        "prior_recommendation": {
            "what": "Shift to a 70/30 stock/bond split using VTI, BND and NVDA",
            "target_allocation": {"stocks": 70, "bonds": 30},
            "suggested_instruments": ["VTI", "BND", "NVDA"],
        },
        "active_constraints": {"exclusions": ["remove NVIDIA"], "tilts": [], "other": []},
        "user_message": "more bonds",
        "turn_number": 2,
    }

    result = refinement_graph.invoke(state)

    assert result["active_constraints"]["exclusions"] == ["remove NVIDIA"]
    assert result["active_constraints"]["tilts"] == ["more bonds"]
    assert result["new_recommendation"] == CANNED_OUTPUT.model_dump()
    assert result["llm_provider"] == "fake"
