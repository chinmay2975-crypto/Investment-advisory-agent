from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.refinement.graph import refinement_graph
from app.db.models import (
    Goal,
    Investor,
    InvestorProfile,
    Recommendation,
    RefinementMessage,
    RefinementSession,
)
from app.db.session import get_db
from app.dependencies import require_self
from app.schemas.recommendation import RecommendationRead
from app.schemas.refinement import RefinementRequest, RefinementSessionRead
from app.services.allocation import get_default_allocation
from app.services.chroma_client import query_context
from app.services.goal_simulation import apply_goal_simulation
from app.services.goal_analysis import GoalAnalysisError, analyze_goal

router = APIRouter(
    prefix="/investors/{investor_id}/recommendations/{recommendation_id}",
    tags=["refinement"],
    dependencies=[Depends(require_self)],
)


def _to_dict(model, fields: list[str]) -> dict:
    return {field: getattr(model, field) for field in fields}


def _find_session(db: Session, recommendation_id: int) -> RefinementSession | None:
    session = (
        db.query(RefinementSession)
        .filter(RefinementSession.current_recommendation_id == recommendation_id)
        .first()
    )
    if session is not None:
        return session

    is_stale_origin = (
        db.query(RefinementSession)
        .filter(RefinementSession.origin_recommendation_id == recommendation_id)
        .first()
    )
    if is_stale_origin is not None:
        return is_stale_origin

    stale_message = (
        db.query(RefinementMessage)
        .filter(RefinementMessage.resulting_recommendation_id == recommendation_id)
        .first()
    )
    if stale_message is not None:
        return db.get(RefinementSession, stale_message.session_id)

    return None


@router.post("/refine", response_model=RecommendationRead)
def refine_recommendation(
    investor_id: int, recommendation_id: int, body: RefinementRequest, db: Session = Depends(get_db)
):
    investor = db.get(Investor, investor_id)
    if investor is None:
        raise HTTPException(status_code=404, detail="Investor not found")

    recommendation = (
        db.query(Recommendation)
        .filter(Recommendation.investor_id == investor_id, Recommendation.id == recommendation_id)
        .first()
    )
    if recommendation is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    if recommendation.goal_id is None:
        raise HTTPException(status_code=400, detail="Recommendation has no associated goal to refine against")

    session = _find_session(db, recommendation_id)
    if session is not None and session.current_recommendation_id != recommendation_id:
        raise HTTPException(
            status_code=409,
            detail="This recommendation is no longer current for its refinement session; "
            f"refine off recommendation {session.current_recommendation_id} instead",
        )

    profile = db.query(InvestorProfile).filter(InvestorProfile.investor_id == investor_id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Investor profile not found")

    goal = db.query(Goal).filter(Goal.investor_id == investor_id, Goal.id == recommendation.goal_id).first()
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

    active_constraints = session.active_constraints if session is not None else {}
    turn_number = len(session.messages) + 1 if session is not None else 1

    state = {
        "profile": profile_dict,
        "goal": goal_dict,
        "goal_analysis": goal_analysis,
        "default_allocation": default_allocation,
        "context_docs": context_docs,
        "prior_recommendation": recommendation.payload,
        "active_constraints": active_constraints,
        "user_message": body.message,
        "turn_number": turn_number,
    }
    result = refinement_graph.invoke(state)

    new_recommendation = Recommendation(
        investor_id=investor_id,
        goal_id=goal.id,
        status="pending",
        payload=apply_goal_simulation(result["new_recommendation"], goal_dict, profile.country),
        llm_provider=result["llm_provider"],
    )
    db.add(new_recommendation)
    db.flush()

    if session is None:
        session = RefinementSession(
            investor_id=investor_id,
            goal_id=goal.id,
            origin_recommendation_id=recommendation_id,
            current_recommendation_id=new_recommendation.id,
            active_constraints=result["active_constraints"],
        )
        db.add(session)
        db.flush()
    else:
        session.current_recommendation_id = new_recommendation.id
        session.active_constraints = result["active_constraints"]

    db.add(
        RefinementMessage(
            session_id=session.id,
            turn_number=turn_number,
            user_message=body.message,
            resulting_recommendation_id=new_recommendation.id,
            llm_provider=result["llm_provider"],
        )
    )
    db.commit()
    db.refresh(new_recommendation)
    return new_recommendation


@router.get("/refinement-session", response_model=RefinementSessionRead)
def get_refinement_session(investor_id: int, recommendation_id: int, db: Session = Depends(get_db)):
    recommendation = (
        db.query(Recommendation)
        .filter(Recommendation.investor_id == investor_id, Recommendation.id == recommendation_id)
        .first()
    )
    if recommendation is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    session = _find_session(db, recommendation_id)
    if session is None:
        raise HTTPException(status_code=404, detail="No refinement session found for this recommendation")
    return session
