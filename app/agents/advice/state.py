from typing import TypedDict


class AdviceState(TypedDict, total=False):
    profile: dict
    goal: dict | None
    goal_analysis: dict | None
    default_allocation: dict
    analysis_request: dict  # PortfolioAnalyzeRequest as a dict
    portfolio_analysis: dict | None  # PortfolioAnalyzeResponse as a dict
    country_code: str
    country_context: dict  # rendered generically into the prompt; never branched on
    context_docs: list[dict]
    recommendation: dict
    llm_provider: str
