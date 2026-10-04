from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.recommendation import RecommendationRead


class ScenarioRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    investor_id: int
    goal_id: int
    created_at: datetime
    conservative_recommendation: RecommendationRead
    balanced_recommendation: RecommendationRead
    aggressive_recommendation: RecommendationRead
