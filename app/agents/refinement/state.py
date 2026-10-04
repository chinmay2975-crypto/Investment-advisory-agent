from typing import TypedDict


class RefinementState(TypedDict, total=False):
    profile: dict
    goal: dict
    goal_analysis: dict | None
    default_allocation: dict
    context_docs: list[dict]
    prior_recommendation: dict
    active_constraints: dict  # {"exclusions": [...], "tilts": [...], "other": [...]}
    user_message: str
    turn_number: int
    new_recommendation: dict
    llm_provider: str
