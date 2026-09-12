from app.llm.base import LLMClient
from app.llm.router import LLMRouter
from app.schemas.recommendation import RecommendationOutput
from app.services.recommendation_engine import generate_recommendation

CANNED_OUTPUT = RecommendationOutput(
    what="Shift to a 70/30 stock/bond split using VTI and BND",
    target_allocation={"stocks": 70, "bonds": 30},
    suggested_instruments=["VTI", "BND"],
    why="Balances growth needed to meet the goal with the investor's risk cadence",
    expected_behavior="Expected to grow with market volatility, smoothed by bond allocation",
    goal_probability=0.82,
    risks=["Market downturn risk", "Inflation eroding real returns"],
)


class FakeClient(LLMClient):
    name = "fake"

    def generate(self, prompt, schema):
        assert schema is RecommendationOutput
        return CANNED_OUTPUT


def test_generate_recommendation_returns_output_and_provider():
    router = LLMRouter([FakeClient()])

    output, provider_name = generate_recommendation("any prompt", router)

    assert output == CANNED_OUTPUT
    assert provider_name == "fake"
