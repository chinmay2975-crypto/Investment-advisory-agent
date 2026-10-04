from app.agents.refinement.state import RefinementState
from app.llm.factory import get_router
from app.schemas.recommendation import RecommendationOutput
from app.services.recommendation_engine import build_refinement_prompt

EXCLUSION_KEYWORDS = ("remove", "exclude", "drop", "avoid", "no more", "don't want", "get rid of")
TILT_KEYWORDS = ("more", "less", "increase", "decrease", "higher", "lower", "shift", "reduce", "add")


def _empty_constraints() -> dict:
    return {"exclusions": [], "tilts": [], "other": []}


def classify_constraint_node(state: RefinementState) -> dict:
    """Buckets the free-text refinement message into a structured category and
    merges it into the running constraint accumulator so prior turns' constraints
    are never dropped. Rule-based for now; swappable for an LLM classifier later
    without changing the graph shape.
    """
    message = state.get("user_message", "")
    lowered = message.lower()

    constraints = {
        key: list(values) for key, values in (state.get("active_constraints") or _empty_constraints()).items()
    }
    for key in ("exclusions", "tilts", "other"):
        constraints.setdefault(key, [])

    if any(keyword in lowered for keyword in EXCLUSION_KEYWORDS):
        bucket = "exclusions"
    elif any(keyword in lowered for keyword in TILT_KEYWORDS):
        bucket = "tilts"
    else:
        bucket = "other"

    if message and message not in constraints[bucket]:
        constraints[bucket].append(message)

    return {"active_constraints": constraints}


def refine_recommendation_node(state: RefinementState) -> dict:
    prompt = build_refinement_prompt(
        profile=state["profile"],
        goal=state["goal"],
        goal_analysis=state.get("goal_analysis"),
        context_docs=state.get("context_docs") or [],
        default_allocation=state["default_allocation"],
        prior_recommendation=state["prior_recommendation"],
        active_constraints=state.get("active_constraints") or _empty_constraints(),
        user_message=state.get("user_message", ""),
        turn_number=state.get("turn_number", 1),
    )
    output, provider_name = get_router().generate(prompt, RecommendationOutput)
    return {"new_recommendation": output.model_dump(), "llm_provider": provider_name}
