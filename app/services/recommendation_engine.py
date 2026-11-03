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


def _grounding_sections(
    profile: dict,
    goal: dict,
    goal_analysis: dict | None,
    context_docs: list[dict],
) -> tuple[str, str]:
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

    return goal_analysis_section, context_section


def build_prompt(
    profile: dict,
    goal: dict,
    goal_analysis: dict | None,
    context_docs: list[dict],
    default_allocation: dict,
) -> str:
    goal_analysis_section, context_section = _grounding_sections(profile, goal, goal_analysis, context_docs)

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


REFINEMENT_TEMPLATE = """You are an investment advisory assistant refining a previous structured recommendation
based on the investor's follow-up request.

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

PRIOR RECOMMENDATION (turn {prior_turn_number})
- What: {prior_what}
- Target allocation: {prior_allocation}
- Instruments: {prior_instruments}

ACTIVE CONSTRAINTS FROM THIS CONVERSATION (must all still be honored, not just the newest one)
- Exclusions: {exclusions}
- Tilts: {tilts}
- Other: {other}

USER'S NEW REFINEMENT REQUEST
"{user_message}"

INSTRUCTIONS
Produce an updated structured recommendation that satisfies ALL active constraints above plus the
new request, while staying grounded in the same investor profile, goal, and market context. Keep
these strictly separate:
- `what`: the concrete recommended action — a short summary plus target_allocation (percentages by
  asset class) and suggested_instruments (specific funds/ETFs/tickers).
- `why`: the rationale, grounded in the investor profile, goal, market context, and how this
  addresses the refinement request without dropping earlier constraints.
- `expected_behavior`: how this recommendation is expected to behave (an estimate/projection, not a
  guarantee).
- `goal_probability`: your estimated probability (0.0-1.0) that this recommendation meets the goal
  by the target date.
- `risks`: a list of specific risks or caveats.
Do not blend rationale, prediction, or fact into `what` — keep it purely the recommended action.
"""


def build_refinement_prompt(
    profile: dict,
    goal: dict,
    goal_analysis: dict | None,
    context_docs: list[dict],
    default_allocation: dict,
    prior_recommendation: dict,
    active_constraints: dict,
    user_message: str,
    turn_number: int,
) -> str:
    goal_analysis_section, context_section = _grounding_sections(profile, goal, goal_analysis, context_docs)

    return REFINEMENT_TEMPLATE.format(
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
        prior_turn_number=turn_number - 1 if turn_number > 1 else 1,
        prior_what=prior_recommendation.get("what"),
        prior_allocation=prior_recommendation.get("target_allocation"),
        prior_instruments=prior_recommendation.get("suggested_instruments"),
        exclusions=active_constraints.get("exclusions") or [],
        tilts=active_constraints.get("tilts") or [],
        other=active_constraints.get("other") or [],
        user_message=user_message,
    )


def generate_recommendation(prompt: str, router: LLMRouter) -> tuple[RecommendationOutput, str]:
    return router.generate(prompt, RecommendationOutput)


ADVICE_TEMPLATE = """You are an investment information assistant producing a structured, general-information
portfolio suggestion. You are not a licensed adviser; frame everything as general information.

MARKET / COUNTRY CONTEXT (use these conventions; quote amounts in {currency})
- Country: {country_name} ({country_code}), currency {currency}
- Local benchmark: {benchmark_name} ({benchmark_ticker})
- Risk-free rate proxy: {risk_free_label} = {risk_free_rate:.2%} ({risk_free_source})
- Capital gains rules ({tax_as_of}, general information only):
{tax_summary}
- Common tax-advantaged accounts: {accounts}

INVESTOR PROFILE
- Risk cadence: {risk_cadence}
- Horizon: {horizon_years} years
- Preferences: {preferences}
- Restrictions: {restrictions}
- Default allocation template for this risk cadence: {default_allocation}

GOAL
{goal_section}
CURRENT PORTFOLIO ANALYSIS
{portfolio_section}

MARKET CONTEXT (retrieved, cite what you use and its source/date; do not treat as guaranteed future fact)
{context_section}

INSTRUCTIONS
Respond with a structured suggestion. Keep these strictly separate:
- `what`: the concrete suggested action -- a short summary plus target_allocation (percentages by asset
  class) and suggested_instruments (funds/ETFs/tickers listed in {country_name} where possible).
- `why`: the rationale, grounded in the profile, goal, current portfolio analysis and market context,
  referencing the local benchmark, risk-free rate and tax-advantaged accounts where relevant.
- `expected_behavior`: how this is expected to behave (an estimate, not a guarantee).
- `goal_probability`: estimated probability (0.0-1.0) of meeting the goal (0.5 if no goal is set).
- `risks`: specific risks and caveats, including currency risk for any non-{currency} exposure.
Do not blend rationale, prediction, or fact into `what`.
"""


def _goal_section(goal: dict | None, goal_analysis: dict | None) -> str:
    if not goal:
        return "- No specific goal selected; give general long-term guidance for this profile.\n"
    lines = (
        f"- Category: {goal.get('category')}\n"
        f"- Target amount: {goal.get('target_amount')}\n"
        f"- Current amount: {goal.get('current_amount')}\n"
        f"- Target date: {goal.get('target_date')}\n"
    )
    goal_analysis_section, _ = _grounding_sections({}, goal, goal_analysis, [])
    return lines + goal_analysis_section


def _portfolio_section(analysis: dict | None) -> str:
    if not analysis or not analysis.get("holdings"):
        return "- No current holdings provided.\n"

    def pct(value) -> str:
        return "n/a" if value is None else f"{value:.2%}"

    currency = analysis["base_currency"]
    lines = [
        f"- Total value: {analysis['total_value_base']:,.2f} {currency}",
        f"- Allocation by country: {analysis['allocation_by_country']}",
        f"- Allocation by asset class: {analysis['allocation_by_asset_class']}",
        f"- Allocation by sector: {analysis['allocation_by_sector']}",
        f"- Currency exposure: {analysis['currency_exposure']}",
    ]
    metrics = analysis.get("combined_metrics")
    if metrics:
        lines.append(
            f"- {analysis['lookback']} return {pct(metrics['total_return'])} vs {metrics['benchmark_name']} "
            f"{pct(metrics['benchmark_total_return'])}; volatility {pct(metrics['annualized_volatility'])}; "
            f"Sharpe {metrics['sharpe_ratio']}; beta {metrics['beta']}; max drawdown {pct(metrics['max_drawdown'])}"
        )
    concentration = analysis.get("concentration")
    if concentration:
        lines.append(
            f"- Concentration: HHI {concentration['hhi']:.3f}, largest position "
            f"{concentration['largest_position_ticker']} at {pct(concentration['largest_position_weight'])}"
        )
    top = sorted(analysis["holdings"], key=lambda h: h["weight"] or 0, reverse=True)[:10]
    lines.append("- Top holdings: " + ", ".join(f"{h['ticker']} {pct(h['weight'])}" for h in top))
    return "\n".join(lines) + "\n"


def build_advice_prompt(
    profile: dict,
    goal: dict | None,
    goal_analysis: dict | None,
    context_docs: list[dict],
    default_allocation: dict,
    country_context: dict,
    portfolio_analysis: dict | None,
) -> str:
    _, context_section = _grounding_sections(profile, goal or {}, None, context_docs)
    return ADVICE_TEMPLATE.format(
        country_name=country_context["name"],
        country_code=country_context["code"],
        currency=country_context["currency"],
        benchmark_name=country_context["benchmark_name"],
        benchmark_ticker=country_context["benchmark_ticker"],
        risk_free_label=country_context["risk_free_label"],
        risk_free_rate=country_context["risk_free_rate"],
        risk_free_source=country_context["risk_free_source"],
        tax_as_of=country_context["tax_as_of"],
        tax_summary="\n".join(f"  - {line}" for line in country_context["tax_summary"]),
        accounts=", ".join(country_context["tax_advantaged_accounts"]),
        risk_cadence=profile.get("risk_cadence"),
        horizon_years=profile.get("horizon_years"),
        preferences=profile.get("preferences") or {},
        restrictions=profile.get("restrictions") or {},
        default_allocation=default_allocation,
        goal_section=_goal_section(goal, goal_analysis),
        portfolio_section=_portfolio_section(portfolio_analysis),
        context_section=context_section,
    )
