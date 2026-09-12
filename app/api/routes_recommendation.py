from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Goal, Investor, InvestorProfile, Recommendation
from app.db.session import get_db
from app.llm.factory import get_router
from app.schemas.recommendation import RecommendationRead
from app.services.allocation import get_default_allocation
from app.services.chroma_client import query_context
from app.services.goal_analysis import analyze_goal, GoalAnalysisError
from app.services.recommendation_engine import build_prompt, generate_recommendation

router = APIRouter(prefix="/investors/{investor_id}/recommendations", tags=["recommendations"])


def _to_dict(model, fields: list[str]) -> dict:
    return {field: getattr(model, field) for field in fields}


@router.post("/", response_model=RecommendationRead)
def create_recommendation(investor_id: int, goal_id: int, db: Session = Depends(get_db)):
    investor = db.get(Investor, investor_id)
    if investor is None:
        raise HTTPException(status_code=404, detail="Investor not found")

    profile = db.query(InvestorProfile).filter(InvestorProfile.investor_id == investor_id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Investor profile not found")

    goal = db.query(Goal).filter(Goal.investor_id == investor_id, Goal.id == goal_id).first()
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")

    try:
        goal_analysis = analyze_goal(goal)
    except GoalAnalysisError:
        goal_analysis = None

    try:
        default_allocation = get_default_allocation(profile.risk_cadence)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    context_docs = query_context(f"{goal.category} investing outlook for a {profile.risk_cadence} investor")

    profile_dict = _to_dict(profile, ["risk_cadence", "horizon_years", "preferences", "restrictions"])
    goal_dict = _to_dict(
        goal,
        [
            "category",
            "target_amount",
            "current_amount",
            "target_date",
            "contribution_cadence",
            "contribution_amount",
        ],
    )

    prompt = build_prompt(profile_dict, goal_dict, goal_analysis, context_docs, default_allocation)
    output, provider_name = generate_recommendation(prompt, get_router())

    recommendation = Recommendation(
        investor_id=investor_id,
        goal_id=goal_id,
        status="pending",
        payload=output.model_dump(),
        llm_provider=provider_name,
    )
    db.add(recommendation)
    db.commit()
    db.refresh(recommendation)
    return recommendation


@router.get("/", response_model=list[RecommendationRead])
def list_recommendations(investor_id: int, db: Session = Depends(get_db)):
    return db.query(Recommendation).filter(Recommendation.investor_id == investor_id).all()


@router.get("/{recommendation_id}", response_model=RecommendationRead)
def get_recommendation(investor_id: int, recommendation_id: int, db: Session = Depends(get_db)):
    recommendation = (
        db.query(Recommendation)
        .filter(Recommendation.investor_id == investor_id, Recommendation.id == recommendation_id)
        .first()
    )
    if recommendation is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return recommendation
