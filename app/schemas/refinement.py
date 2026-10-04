from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RefinementRequest(BaseModel):
    message: str


class RefinementMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    turn_number: int
    user_message: str
    resulting_recommendation_id: int
    llm_provider: str | None
    created_at: datetime


class RefinementSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    investor_id: int
    goal_id: int
    origin_recommendation_id: int
    current_recommendation_id: int
    active_constraints: dict
    status: str
    created_at: datetime
    updated_at: datetime
    messages: list[RefinementMessageRead] = []
