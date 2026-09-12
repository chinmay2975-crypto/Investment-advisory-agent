from pydantic import BaseModel


class RecommendationOutput(BaseModel):
    """Structured shape every LLM-generated recommendation must conform to.

    Keeps fact vs. assumption vs. prediction structurally separate rather
    than relying on prose, per the tech-stack doc's Recommendation Engine
    requirements.
    """

    what: str
    why: str
    expected_behavior: str
    goal_probability: float
    risks: list[str]
