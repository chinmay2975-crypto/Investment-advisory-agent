import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.agents.advice.graph import ADVICE_STAGES, advice_graph
from app.countries import UnknownCountryError, normalize_country_code
from app.countries.base import GENERAL_INFORMATION_NOTICE
from app.db.models import Goal, Holding, Investor, InvestorProfile, Recommendation
from app.db.session import get_db
from app.dependencies import get_current_investor
from app.schemas.analysis import Lookback, PortfolioHoldingIn
from app.services.allocation import get_default_allocation
from app.services.goal_simulation import apply_goal_simulation
from app.services.goal_analysis import GoalAnalysisError, analyze_goal

router = APIRouter(prefix="/advice", tags=["advice"])

SECTIONS = [
    ("what", "Suggested action"),
    ("target_allocation", "Target allocation"),
    ("suggested_instruments", "Example instruments"),
    ("why", "Why"),
    ("expected_behavior", "Expected behaviour (estimate, not a guarantee)"),
    ("goal_probability", "Estimated goal probability"),
    ("risks", "Risks and caveats"),
]

SSE_EXAMPLE = (
    'event: stage\ndata: {"stage": "analyze_portfolio", "label": "Analysing your portfolio", "status": "started"}\n\n'
    'event: stage\ndata: {"stage": "analyze_portfolio", "label": "Analysing your portfolio", "status": "completed"}\n\n'
    'event: context\ndata: {"country": "IN", "country_name": "India", "currency": "INR", "source": "inferred"}\n\n'
    'event: section\ndata: {"key": "what", "title": "Suggested action", "content": "..."}\n\n'
    'event: done\ndata: {"recommendation_id": 42, "llm_provider": "gemini"}\n\n'
)


class AdviceRequest(BaseModel):
    goal_id: int | None = Field(default=None, description="Optional goal to plan against")
    holdings: list[PortfolioHoldingIn] | None = Field(
        default=None, description="Omit to use the holdings saved on your account"
    )
    country: str | None = Field(default=None, description="Override; defaults to profile country, then inference")
    base_currency: str | None = None
    lookback: Lookback = "1y"

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"goal_id": None, "holdings": None, "country": None, "base_currency": None, "lookback": "1y"},
                {
                    "holdings": [{"ticker": "RELIANCE.NS", "quantity": 20}, {"ticker": "TCS.NS", "quantity": 10}],
                    "country": "IN",
                    "base_currency": "INR",
                    "lookback": "1y",
                },
            ]
        }
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@router.post(
    "/stream",
    summary="Stream a country-aware portfolio suggestion (Server-Sent Events)",
    description=(
        "Runs the advice LangGraph agent and streams `stage` events as each step runs, a `context` "
        "event with the resolved country, one `section` event per part of the suggestion, then `done` "
        "(with the saved recommendation id) or `error`. Swagger shows the full stream once it finishes. "
        "General information only, not licensed financial advice."
    ),
    responses={200: {"content": {"text/event-stream": {"example": SSE_EXAMPLE}}}},
)
def stream_advice(
    payload: AdviceRequest,
    investor: Investor = Depends(get_current_investor),
    db: Session = Depends(get_db),
):
    profile = db.query(InvestorProfile).filter(InvestorProfile.investor_id == investor.id).first()
    if profile is None:
        raise HTTPException(status_code=400, detail="Set up your investor profile first")

    goal_dict = None
    goal_analysis = None
    if payload.goal_id is not None:
        goal = db.query(Goal).filter(Goal.investor_id == investor.id, Goal.id == payload.goal_id).first()
        if goal is None:
            raise HTTPException(status_code=404, detail="Goal not found")
        goal_dict = {
            field: getattr(goal, field)
            for field in (
                "category",
                "target_amount",
                "current_amount",
                "target_date",
                "contribution_cadence",
                "contribution_amount",
            )
        }
        try:
            goal_analysis = analyze_goal(goal)
        except GoalAnalysisError:
            goal_analysis = None

    if payload.holdings is not None:
        holdings = payload.holdings
    else:
        holdings = [
            PortfolioHoldingIn(ticker=h.ticker, quantity=h.quantity, cost_basis=h.cost_basis)
            for h in db.query(Holding).filter(Holding.investor_id == investor.id).all()
        ]

    country = payload.country or profile.country
    try:
        country = normalize_country_code(country) if country else None
        default_allocation = get_default_allocation(profile.risk_cadence)
    except (UnknownCountryError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not holdings and not country:
        raise HTTPException(status_code=400, detail="No holdings found; select a country to get country-specific guidance")

    initial_state = {
        "profile": {
            "risk_cadence": profile.risk_cadence,
            "horizon_years": profile.horizon_years,
            "preferences": profile.preferences,
            "restrictions": profile.restrictions,
        },
        "goal": goal_dict,
        "goal_analysis": goal_analysis,
        "default_allocation": default_allocation,
        "analysis_request": {
            "holdings": [h.model_dump() for h in holdings],
            "country": country,
            "base_currency": payload.base_currency or profile.base_currency,
            "lookback": payload.lookback,
        },
    }
    labels = dict(ADVICE_STAGES)
    order = [name for name, _ in ADVICE_STAGES]

    def events() -> Iterator[str]:
        state = dict(initial_state)
        yield _sse("stage", {"stage": order[0], "label": labels[order[0]], "status": "started"})
        try:
            for update in advice_graph.stream(initial_state, stream_mode="updates"):
                for node, delta in update.items():
                    state.update(delta or {})
                    yield _sse("stage", {"stage": node, "label": labels[node], "status": "completed"})
                    if node == "load_country_context":
                        analysis = state.get("portfolio_analysis") or {}
                        ctx = state["country_context"]
                        yield _sse(
                            "context",
                            {
                                "country": ctx["code"],
                                "country_name": ctx["name"],
                                "currency": ctx["currency"],
                                "benchmark_name": ctx["benchmark_name"],
                                "source": (analysis.get("country") or {}).get("source", "user_selected"),
                                "warnings": analysis.get("warnings", []),
                            },
                        )
                    position = order.index(node)
                    if position + 1 < len(order):
                        following = order[position + 1]
                        yield _sse("stage", {"stage": following, "label": labels[following], "status": "started"})

            recommendation = apply_goal_simulation(state["recommendation"], goal_dict, state["country_code"])
            for key, title in SECTIONS:
                if key == "goal_probability":
                    title = (
                        "Goal probability (simulated over 5,000 market paths)"
                        if recommendation.get("goal_probability_method") == "monte_carlo"
                        else "Goal probability (model estimate — no goal selected)"
                    )
                yield _sse("section", {"key": key, "title": title, "content": recommendation[key]})
            yield _sse(
                "section",
                {
                    "key": "disclaimer",
                    "title": "Important",
                    "content": f"{state['country_context']['regulatory_disclaimer']} {GENERAL_INFORMATION_NOTICE}",
                },
            )

            saved = Recommendation(
                investor_id=investor.id,
                goal_id=payload.goal_id,
                status="pending",
                payload=recommendation,
                llm_provider=state["llm_provider"],
            )
            db.add(saved)
            db.commit()
            db.refresh(saved)
            yield _sse("done", {"recommendation_id": saved.id, "llm_provider": state["llm_provider"]})
        except Exception as exc:  # surfaced to the client as an SSE event; the HTTP status is already 200
            db.rollback()
            yield _sse("error", {"message": str(exc) or exc.__class__.__name__})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
