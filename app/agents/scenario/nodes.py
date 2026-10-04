from app.agents.scenario.state import ScenarioState
from app.llm.factory import get_router
from app.schemas.recommendation import RecommendationOutput
from app.services.allocation import get_default_allocation
from app.services.recommendation_engine import build_prompt

VARIANTS = ["conservative", "balanced", "aggressive"]
VARIANT_RISK_CADENCE = {
    "conservative": "Conservative",
    "balanced": "Balanced",
    "aggressive": "Aggressive",
}


def _run_variant(state: ScenarioState, variant: str) -> dict:
    risk_cadence = VARIANT_RISK_CADENCE[variant]
    variant_profile = {**state["profile"], "risk_cadence": risk_cadence}
    default_allocation = get_default_allocation(risk_cadence)

    prompt = build_prompt(
        variant_profile,
        state["goal"],
        state.get("goal_analysis"),
        state.get("context_docs") or [],
        default_allocation,
    )
    output, provider_name = get_router().generate(prompt, RecommendationOutput)
    return {variant: output.model_dump(), f"{variant}_provider": provider_name}


def conservative_node(state: ScenarioState) -> dict:
    return _run_variant(state, "conservative")


def balanced_node(state: ScenarioState) -> dict:
    return _run_variant(state, "balanced")


def aggressive_node(state: ScenarioState) -> dict:
    return _run_variant(state, "aggressive")
