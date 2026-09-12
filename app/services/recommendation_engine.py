from app.llm.router import LLMRouter
from app.schemas.recommendation import RecommendationOutput

PROMPT_TEMPLATE = """You are an investment advisory assistant generating a structured recommendation.

INVESTOR PROFILE
- Risk cadence: {risk_cadence}
- Horizon: {horizon_years} years
- Preferences: {preferences}
- Restrictions: {restrictions}
- Default allocation template for this risk cadence: {default_allocation}

GOAL
- Category: {goal_category}
- Target amount: {target_amount}
- Current amount: {current_amount}
- Target date: {target_date}
{goal_analysis_section}
MARKET CONTEXT (retrieved, cite what you use and its source/date; do not treat as guaranteed future fact)
{context_section}

INSTRUCTIONS
Respond with a structured recommendation. Keep these strictly separate:
- `what`: the concrete recommended action — a short summary plus target_allocation (percentages by asset class) and suggested_instruments (specific funds/ETFs/tickers).
- `why`: the rationale, grounded in the investor profile, goal, and the market context above.
- `expected_behavior`: how this recommendation is expected to behave (an estimate/projection, not a guarantee).
- `goal_probability`: your estimated probability (0.0-1.0) that this recommendation meets the goal by the target date.
- `risks`: a list of specific risks or caveats, including anything from the market context that could invalidate the assumptions above.
Do not blend rationale, prediction, or fact into `what` — keep it purely the recommended action.
"""


def build_prompt(
    profile: dict,
    goal: dict,
    goal_analysis: dict | None,
    context_docs: list[dict],
    default_allocation: dict,
) -> str:
    if goal_analysis:
        goal_analysis_section = (
            f"- Contribution: {goal['contribution_amount']} per {goal.get('contribution_cadence')}\n"
            f"- Required annual return to meet goal: {goal_analysis['required_annual_return']:.4f}\n"
            f"- Projected value at {goal_analysis['assumed_annual_return']:.4f} assumed return: "
            f"{goal_analysis['projected_value']:.2f}\n"
            f"- Contributions currently sufficient: {goal_analysis['is_sufficient']}\n"
        )
    else:
        goal_analysis_section = "- No contribution plan set; goal sufficiency not computed.\n"

    if context_docs:
        context_section = "\n".join(
            f"- [{doc['metadata'].get('category', 'unknown')} | {doc['metadata'].get('source', 'unknown')} "
            f"| as of {doc['metadata'].get('as_of', 'unknown')}] {doc['text']}"
            for doc in context_docs
        )
    else:
        context_section = "- No market context retrieved."

    return PROMPT_TEMPLATE.format(
        risk_cadence=profile.get("risk_cadence"),
        horizon_years=profile.get("horizon_years"),
        preferences=profile.get("preferences") or {},
        restrictions=profile.get("restrictions") or {},
        default_allocation=default_allocation,
        goal_category=goal.get("category"),
        target_amount=goal.get("target_amount"),
        current_amount=goal.get("current_amount"),
        target_date=goal.get("target_date"),
        goal_analysis_section=goal_analysis_section,
        context_section=context_section,
    )


def generate_recommendation(prompt: str, router: LLMRouter) -> tuple[RecommendationOutput, str]:
    return router.generate(prompt, RecommendationOutput)
