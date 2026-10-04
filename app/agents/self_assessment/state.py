from typing import TypedDict


class SelfAssessmentState(TypedDict, total=False):
    recommendation_payload: dict
    generated_at: str
    deviation: dict
    similar_reflections: list[dict]
    contributing_factors: str
    assumptions_held: bool
    reflection_summary: str
    llm_provider: str
