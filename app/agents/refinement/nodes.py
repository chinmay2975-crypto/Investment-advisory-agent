from pydantic import BaseModel, Field

from app.agents.refinement.state import RefinementState
from app.llm.base import ProviderError
from app.llm.factory import get_router
from app.schemas.recommendation import RecommendationOutput
from app.services.recommendation_engine import build_refinement_prompt

EXCLUSION_KEYWORDS = ("remove", "exclude", "drop", "avoid", "no more", "don't want", "get rid of")
TILT_KEYWORDS = ("more", "less", "increase", "decrease", "higher", "lower", "shift", "reduce", "add")
BUCKETS = ("exclusions", "tilts", "other")


class ConstraintSplit(BaseModel):
    exclusions: list[str] = Field(default_factory=list)
    tilts: list[str] = Field(default_factory=list)
    other: list[str] = Field(default_factory=list)
    remove_previous: list[str] = Field(default_factory=list)


SPLIT_PROMPT = """Split an investor's request for changing a portfolio suggestion into separate, atomic
constraints.
- exclusions: holdings, sectors or asset types to remove or avoid, each as a short phrase
  (e.g. "Apple (AAPL)", "tobacco stocks").
- tilts: directional changes, each as a short phrase (e.g. "more bonds", "less US exposure").
- other: any other requirement (e.g. "only ETFs", "keep it under 5 funds").
- remove_previous: constraints from the CURRENT list below that this request cancels (e.g. "actually,
  keep Apple" cancels "Apple (AAPL)"); copy them exactly as written there.
One request may produce several entries. Don't invent constraints the investor didn't ask for.

CURRENT CONSTRAINTS: {current}
REQUEST: "{message}"
"""


def _empty_constraints() -> dict:
    return {key: [] for key in BUCKETS}


def _llm_split(message: str, current: dict) -> ConstraintSplit | None:
    """None when no LLM is reachable; the caller falls back to keyword rules."""
    try:
        split, _ = get_router().generate(SPLIT_PROMPT.format(current=current, message=message), ConstraintSplit)
    except ProviderError:
        return None
    return split if isinstance(split, ConstraintSplit) else None


def _keyword_split(message: str) -> ConstraintSplit:
    lowered = message.lower()
    if any(keyword in lowered for keyword in EXCLUSION_KEYWORDS):
        return ConstraintSplit(exclusions=[message])
    if any(keyword in lowered for keyword in TILT_KEYWORDS):
        return ConstraintSplit(tilts=[message])
    return ConstraintSplit(other=[message])


def classify_constraint_node(state: RefinementState) -> dict:
    """Splits the refinement message into atomic constraints (LLM, with a keyword fallback) and
    merges them into the running accumulator, so earlier turns' constraints persist unless the
    investor explicitly cancels them."""
    message = state.get("user_message", "").strip()
    constraints = {key: list((state.get("active_constraints") or {}).get(key, [])) for key in BUCKETS}
    if not message:
        return {"active_constraints": constraints}

    split = _llm_split(message, constraints) or _keyword_split(message)

    cancelled = {c.strip().lower() for c in split.remove_previous}
    for key in BUCKETS:
        kept = [c for c in constraints[key] if c.strip().lower() not in cancelled]
        for item in getattr(split, key):
            if item.strip() and item.strip().lower() not in {k.lower() for k in kept}:
                kept.append(item.strip())
        constraints[key] = kept
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
