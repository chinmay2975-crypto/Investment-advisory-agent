from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.scenario.graph import scenario_graph
from app.db.models import Goal, Investor, InvestorProfile, Recommendation, ScenarioRun
from app.db.session import get_db
from app.dependencies import require_self
from app.schemas.scenario import ScenarioRunRead
from app.services.chroma_client import query_context
from app.services.goal_simulation import apply_goal_simulation
from app.services.goal_analysis import GoalAnalysisError, analyze_goal

router = APIRouter(
    prefix="/investors/{investor_id}/goals/{goal_id}/scenarios",
    tags=["scenarios"],
    dependencies=[Depends(require_self)],
)


def _to_dict(model, fields: list[str]) -> dict:
    return {field: getattr(model, field) for field in fields}


@router.post("/", response_model=ScenarioRunRead)
def create_scenario_run(investor_id: int, goal_id: int, db: Session = Depends(get_db)):
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

    context_docs = query_context(f"{goal.category} investing outlook across risk cadences")

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

    state = {
        "profile": profile_dict,
        "goal": goal_dict,
        "goal_analysis": goal_analysis,
        "context_docs": context_docs,
    }
    result = scenario_graph.invoke(state)

    recommendations = {}
    for variant in ("conservative", "balanced", "aggressive"):
        recommendation = Recommendation(
            investor_id=investor_id,
            goal_id=goal_id,
            status="pending",
            payload=apply_goal_simulation(result[variant], goal_dict, profile.country),
            llm_provider=result[f"{variant}_provider"],
        )
        db.add(recommendation)
        recommendations[variant] = recommendation
    db.flush()

    scenario_run = ScenarioRun(
        investor_id=investor_id,
        goal_id=goal_id,
        conservative_recommendation_id=recommendations["conservative"].id,
        balanced_recommendation_id=recommendations["balanced"].id,
        aggressive_recommendation_id=recommendations["aggressive"].id,
    )
    db.add(scenario_run)
    db.commit()
    db.refresh(scenario_run)
    return scenario_run


@router.get("/", response_model=list[ScenarioRunRead])
def list_scenario_runs(investor_id: int, goal_id: int, db: Session = Depends(get_db)):
    return (
        db.query(ScenarioRun)
        .filter(ScenarioRun.investor_id == investor_id, ScenarioRun.goal_id == goal_id)
        .all()
    )


@router.get("/{scenario_run_id}", response_model=ScenarioRunRead)
def get_scenario_run(investor_id: int, goal_id: int, scenario_run_id: int, db: Session = Depends(get_db)):
    scenario_run = (
        db.query(ScenarioRun)
        .filter(
            ScenarioRun.investor_id == investor_id,
            ScenarioRun.goal_id == goal_id,
            ScenarioRun.id == scenario_run_id,
        )
        .first()
    )
    if scenario_run is None:
        raise HTTPException(status_code=404, detail="Scenario run not found")
    return scenario_run
