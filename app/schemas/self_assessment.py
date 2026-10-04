from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReflectionOutput(BaseModel):
    """Structured Reflexion-style self-reflection over a recommendation's realized outcome.

    Kept structured (not free-text) so `assumptions_held` stays a reviewable, queryable
    fact rather than something buried in prose — mirrors how RecommendationOutput keeps
    fact/assumption/prediction separate.
    """

    contributing_factors: str
    assumptions_held: bool
    reflection_summary: str  # short summary embedded into ChromaDB for future retrieval


class EvaluationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recommendation_id: int
    evaluated_at: datetime
    deviation: dict | None
    contributing_factors: str | None
    assumptions_held: bool | None
