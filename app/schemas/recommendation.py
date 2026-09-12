from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RecommendationOutput(BaseModel):
    """Structured shape every LLM-generated recommendation must conform to.

    Keeps fact vs. assumption vs. prediction structurally separate rather
    than relying on prose, per the tech-stack doc's Recommendation Engine
    requirements.
    """

    what: str
    target_allocation: dict[str, float]
    suggested_instruments: list[str]
    why: str
    expected_behavior: str
    goal_probability: float
    risks: list[str]


class RecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    investor_id: int
    goal_id: int | None
    status: str
    payload: dict
    llm_provider: str | None
    generated_at: datetime
