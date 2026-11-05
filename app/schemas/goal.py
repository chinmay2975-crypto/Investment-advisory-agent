from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_GOAL_YEARS = 100
MAX_AMOUNT = 1e13  # far above any real goal; stops overflow-sized numbers


class GoalBase(BaseModel):
    category: str = Field(min_length=1, max_length=60)
    target_amount: float = Field(gt=0, le=MAX_AMOUNT)
    current_amount: float = Field(default=0.0, ge=0, le=MAX_AMOUNT)
    target_date: datetime
    contribution_cadence: str | None = Field(default=None, max_length=20)
    contribution_amount: float | None = Field(default=None, ge=0, le=MAX_AMOUNT)
    goal_risk_override: str | None = Field(default=None, max_length=20)


class GoalCreate(GoalBase):
    @field_validator("target_date")
    @classmethod
    def _reasonable_date(cls, value: datetime) -> datetime:
        now = datetime.now(timezone.utc)
        aware = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if aware <= now:
            raise ValueError("Target date must be in the future")
        if aware > now + timedelta(days=round(365.25 * MAX_GOAL_YEARS)):
            raise ValueError(f"Target date must be within {MAX_GOAL_YEARS} years")
        return value


class GoalRead(GoalBase):  # no date check: a stored goal whose date has passed must still be listed
    model_config = ConfigDict(from_attributes=True)

    id: int
    investor_id: int
    created_at: datetime


class GoalAnalysis(BaseModel):
    required_annual_return: float
    is_sufficient: bool
    projected_value: float
    assumed_annual_return: float
