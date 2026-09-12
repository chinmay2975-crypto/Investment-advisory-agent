from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GoalCreate(BaseModel):
    category: str
    target_amount: float
    current_amount: float = 0.0
    target_date: datetime
    contribution_cadence: str | None = None
    contribution_amount: float | None = None
    goal_risk_override: str | None = None


class GoalRead(GoalCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    investor_id: int
    created_at: datetime


class GoalAnalysis(BaseModel):
    required_annual_return: float
    is_sufficient: bool
    projected_value: float
    assumed_annual_return: float
