from typing import TypedDict


class ScenarioState(TypedDict, total=False):
    profile: dict
    goal: dict
    goal_analysis: dict | None
    context_docs: list[dict]
    conservative: dict
    conservative_provider: str
    balanced: dict
    balanced_provider: str
    aggressive: dict
    aggressive_provider: str
