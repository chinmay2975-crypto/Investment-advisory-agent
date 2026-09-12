from datetime import datetime, timezone

from app.db.models import Goal
from app.services import goal_math

CADENCE_PERIODS_PER_YEAR = {
    "monthly": 12,
    "quarterly": 4,
    "annually": 1,
}
DEFAULT_ASSUMED_RETURN = 0.06


class GoalAnalysisError(ValueError):
    """Raised when a goal can't be analyzed (missing contribution plan, bad cadence, past target date)."""


def analyze_goal(goal: Goal, assumed_annual_return: float = DEFAULT_ASSUMED_RETURN) -> dict:
    if not goal.contribution_cadence or goal.contribution_amount is None:
        raise GoalAnalysisError("Goal must have contribution_cadence and contribution_amount set to analyze")

    periods_per_year = CADENCE_PERIODS_PER_YEAR.get(goal.contribution_cadence.lower())
    if periods_per_year is None:
        raise GoalAnalysisError(
            f"Unknown contribution_cadence '{goal.contribution_cadence}'. "
            f"Expected one of {list(CADENCE_PERIODS_PER_YEAR)}"
        )

    years = (goal.target_date - datetime.now(timezone.utc).replace(tzinfo=None)).days / 365.25
    if years <= 0:
        raise GoalAnalysisError("target_date must be in the future")

    required_return = goal_math.required_annual_return(
        target_amount=goal.target_amount,
        current_amount=goal.current_amount,
        years=years,
        contribution_per_period=goal.contribution_amount,
        periods_per_year=periods_per_year,
    )
    projected_value = goal_math.project_future_value(
        current_amount=goal.current_amount,
        contribution_per_period=goal.contribution_amount,
        annual_return=assumed_annual_return,
        years=years,
        periods_per_year=periods_per_year,
    )
    is_sufficient = goal_math.is_contribution_sufficient(
        target_amount=goal.target_amount,
        current_amount=goal.current_amount,
        years=years,
        contribution_per_period=goal.contribution_amount,
        periods_per_year=periods_per_year,
        assumed_return=assumed_annual_return,
    )

    return {
        "required_annual_return": required_return,
        "is_sufficient": is_sufficient,
        "projected_value": projected_value,
        "assumed_annual_return": assumed_annual_return,
    }
