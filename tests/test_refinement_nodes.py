from app.agents.refinement.nodes import classify_constraint_node, refine_recommendation_node
from app.llm.base import LLMClient, ProviderError
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
        assert schema is RecommendationOutput
        return CANNED_OUTPUT


def test_classify_constraint_node_buckets_exclusion():
    state = {"user_message": "remove NVIDIA from the portfolio", "active_constraints": {}}
    result = classify_constraint_node(state)
    assert result["active_constraints"]["exclusions"] == ["remove NVIDIA from the portfolio"]
    assert result["active_constraints"]["tilts"] == []


def test_classify_constraint_node_buckets_tilt():
    state = {"user_message": "more bonds please", "active_constraints": {}}
    result = classify_constraint_node(state)
    assert result["active_constraints"]["tilts"] == ["more bonds please"]


def test_classify_constraint_node_accumulates_across_turns():
    state = {
        "user_message": "more international exposure",
        "active_constraints": {"exclusions": ["remove NVIDIA"], "tilts": [], "other": []},
    }
    result = classify_constraint_node(state)
    assert result["active_constraints"]["exclusions"] == ["remove NVIDIA"]
    assert result["active_constraints"]["tilts"] == ["more international exposure"]


def test_refine_recommendation_node_returns_output_and_provider(monkeypatch):
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
        "user_message": "remove NVIDIA",
        "turn_number": 2,
    }

    result = refine_recommendation_node(state)

    assert result["new_recommendation"] == CANNED_OUTPUT.model_dump()
    assert result["llm_provider"] == "fake"


# --- LLM constraint splitting ---------------------------------------------------------------

from app.agents.refinement import nodes as refinement_nodes
from app.agents.refinement.nodes import ConstraintSplit

REAL_LLM_SPLIT = refinement_nodes._llm_split  # captured before the autouse fixture patches it


class SplitClient(LLMClient):
    name = "fake"

    def __init__(self, split):
        self.split, self.prompts = split, []

    def generate(self, prompt, schema):
        self.prompts.append(prompt)
        assert schema is ConstraintSplit
        return self.split


def use_llm_split(monkeypatch, split):
    client = SplitClient(split)
    monkeypatch.setattr(refinement_nodes, "_llm_split", REAL_LLM_SPLIT)
    monkeypatch.setattr("app.agents.refinement.nodes.get_router", lambda: LLMRouter([client]))
    return client


def test_mixed_request_is_split_into_separate_constraints(monkeypatch):
    use_llm_split(monkeypatch, ConstraintSplit(exclusions=["Apple (AAPL)"], tilts=["more bonds"]))
    result = classify_constraint_node({"user_message": "remove Apple and add more bonds", "active_constraints": {}})
    assert result["active_constraints"] == {"exclusions": ["Apple (AAPL)"], "tilts": ["more bonds"], "other": []}


def test_later_turn_can_cancel_an_earlier_constraint(monkeypatch):
    client = use_llm_split(monkeypatch, ConstraintSplit(remove_previous=["Apple (AAPL)"], other=["keep it under 5 funds"]))
    state = {
        "user_message": "actually keep Apple, and keep it under 5 funds",
        "active_constraints": {"exclusions": ["Apple (AAPL)", "tobacco stocks"], "tilts": ["more bonds"], "other": []},
    }
    result = classify_constraint_node(state)["active_constraints"]
    assert result == {"exclusions": ["tobacco stocks"], "tilts": ["more bonds"], "other": ["keep it under 5 funds"]}
    assert "Apple (AAPL)" in client.prompts[0]  # current constraints are shown to the model


def test_duplicates_ignored_case_insensitively(monkeypatch):
    use_llm_split(monkeypatch, ConstraintSplit(tilts=["More Bonds"]))
    state = {"user_message": "more bonds please", "active_constraints": {"tilts": ["more bonds"]}}
    assert classify_constraint_node(state)["active_constraints"]["tilts"] == ["more bonds"]


def test_falls_back_to_keywords_when_llm_unavailable(monkeypatch):
    monkeypatch.setattr("app.llm.router.time.sleep", lambda s: None)

    class Down(LLMClient):
        name = "down"

        def generate(self, prompt, schema):
            raise ProviderError("down", status_code=503)

    monkeypatch.setattr(refinement_nodes, "_llm_split", REAL_LLM_SPLIT)
    monkeypatch.setattr("app.agents.refinement.nodes.get_router", lambda: LLMRouter([Down()]))
    result = classify_constraint_node({"user_message": "remove NVIDIA", "active_constraints": {}})
    assert result["active_constraints"]["exclusions"] == ["remove NVIDIA"]
