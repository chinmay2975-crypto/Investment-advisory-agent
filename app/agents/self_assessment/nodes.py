from datetime import datetime

from app.agents.self_assessment.state import SelfAssessmentState
from app.llm.factory import get_router
from app.schemas.self_assessment import ReflectionOutput
from app.services import chroma_client
from app.services.deviation import compute_deviation

REFLECTION_PROMPT_TEMPLATE = """You are the self-assessment module for an investment advisory system,
performing a Reflexion-style reflection over a recommendation made in the past.

ORIGINAL RECOMMENDATION
- What: {what}
- Why: {why}
- Expected behavior: {expected_behavior}
- Estimated goal probability at the time: {goal_probability}
- Risks flagged at the time: {risks}

MEASURED OUTCOME ({elapsed_days} days later)
- Realized average return across suggested instruments: {realized_return_pct:.2f}%
- Return implied by the goal-planning assumption over the same period: {expected_return_pct:.2f}%
- Deviation (realized - expected): {deviation_pct:+.2f} percentage points
- Per-instrument returns: {per_instrument}

SIMILAR PAST EVALUATIONS (retrieved by semantic similarity, for precedent — not ground truth)
{precedent_section}

INSTRUCTIONS
Reflect on why the realized outcome deviated (or didn't) from what was expected. Keep this
grounded and specific:
- `contributing_factors`: concrete factors that likely explain the deviation (or confirm the
  recommendation held up), referencing the measured outcome and any relevant precedent above.
- `assumptions_held`: true only if the recommendation's core assumptions (in `why` and
  `expected_behavior`) still look reasonable given the measured outcome; false if they were
  contradicted.
- `reflection_summary`: a short (1-2 sentence) summary of this outcome, written so it is useful
  as precedent for a *future* similar recommendation.
This is a logged, human-reviewable record only — it does not modify the Recommendation Engine.
"""


def evaluate_node(state: SelfAssessmentState) -> dict:
    generated_at = state["generated_at"]
    if isinstance(generated_at, str):
        generated_at = datetime.fromisoformat(generated_at)
    deviation = compute_deviation(state["recommendation_payload"], generated_at)
    return {"deviation": deviation}


def retrieve_similar_node(state: SelfAssessmentState) -> dict:
    payload = state["recommendation_payload"]
    query_text = f"{payload.get('what', '')} {payload.get('why', '')}"
    similar = chroma_client.query_similar_reflections(query_text, n_results=3)
    return {"similar_reflections": similar}


def build_reflection_prompt(payload: dict, deviation: dict, similar_reflections: list[dict]) -> str:
    if similar_reflections:
        precedent_section = "\n".join(
            f"- [similarity distance {r['distance']:.3f}] {r['text']}" for r in similar_reflections
        )
    else:
        precedent_section = "- No similar past evaluations found yet."

    return REFLECTION_PROMPT_TEMPLATE.format(
        what=payload.get("what"),
        why=payload.get("why"),
        expected_behavior=payload.get("expected_behavior"),
        goal_probability=payload.get("goal_probability"),
        risks=payload.get("risks"),
        elapsed_days=deviation["elapsed_days"],
        realized_return_pct=deviation["realized_return_pct"],
        expected_return_pct=deviation["expected_return_pct"],
        deviation_pct=deviation["deviation_pct"],
        per_instrument=deviation["per_instrument"],
        precedent_section=precedent_section,
    )


def reflect_node(state: SelfAssessmentState) -> dict:
    prompt = build_reflection_prompt(
        state["recommendation_payload"], state["deviation"], state.get("similar_reflections") or []
    )
    output, provider_name = get_router().generate(prompt, ReflectionOutput)
    return {
        "contributing_factors": output.contributing_factors,
        "assumptions_held": output.assumptions_held,
        "reflection_summary": output.reflection_summary,
        "llm_provider": provider_name,
    }
