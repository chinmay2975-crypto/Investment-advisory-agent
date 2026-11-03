from app.agents.advice.state import AdviceState
from app.countries import get_country, resolve_country
from app.llm.factory import get_router
from app.schemas.analysis import PortfolioAnalyzeRequest
from app.schemas.recommendation import RecommendationOutput
from app.services import price_data
from app.services.chroma_client import query_context
from app.services.country_analysis import analyze_portfolio
from app.services.recommendation_engine import build_advice_prompt


def analyze_portfolio_node(state: AdviceState) -> dict:
    request = PortfolioAnalyzeRequest(**state["analysis_request"])
    if not request.holdings:
        # No portfolio: the caller must have supplied a country (resolve_country enforces it).
        return {"portfolio_analysis": None, "country_code": resolve_country([], request.country).effective_country}
    analysis = analyze_portfolio(request)
    return {
        "portfolio_analysis": analysis.model_dump(mode="json"),
        "country_code": analysis.country.effective_country,
    }


def load_country_context_node(state: AdviceState) -> dict:
    country = get_country(state["country_code"])
    risk_free = price_data.fetch_risk_free_rate(country)
    return {
        "country_context": {
            "code": country.code,
            "name": country.name,
            "currency": country.currency,
            "benchmark_name": country.benchmark_name,
            "benchmark_ticker": country.benchmark_ticker,
            "risk_free_label": country.risk_free_rate.label,
            "risk_free_rate": risk_free.rate,
            "risk_free_source": risk_free.source,
            "tax_as_of": country.capital_gains_tax.as_of,
            "tax_summary": list(country.capital_gains_tax.summary),
            "tax_notice": country.capital_gains_tax.notice,
            "tax_advantaged_accounts": [a.name for a in country.tax_advantaged_accounts],
            "regulatory_disclaimer": country.regulatory_disclaimer,
        }
    }


def retrieve_market_context_node(state: AdviceState) -> dict:
    goal = state.get("goal") or {}
    topic = goal.get("category") or "long-term investing"
    query = (
        f"{topic} outlook for a {state['profile'].get('risk_cadence')} investor in "
        f"{state['country_context']['name']}"
    )
    return {"context_docs": query_context(query, n_results=6, country=state["country_code"])}


def generate_advice_node(state: AdviceState) -> dict:
    prompt = build_advice_prompt(
        profile=state["profile"],
        goal=state.get("goal"),
        goal_analysis=state.get("goal_analysis"),
        context_docs=state.get("context_docs") or [],
        default_allocation=state["default_allocation"],
        country_context=state["country_context"],
        portfolio_analysis=state.get("portfolio_analysis"),
    )
    output, provider_name = get_router().generate(prompt, RecommendationOutput)
    return {"recommendation": output.model_dump(), "llm_provider": provider_name}
