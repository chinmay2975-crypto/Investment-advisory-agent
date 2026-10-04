from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HoldingCreate(BaseModel):
    ticker: str
    quantity: float
    cost_basis: float | None = None
    acquired_at: datetime | None = None


class HoldingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    investor_id: int
    ticker: str
    quantity: float
    cost_basis: float | None
    acquired_at: datetime | None
    source: str


class HoldingAnalysis(BaseModel):
    ticker: str
    quantity: float
    cost_basis: float | None
    current_price: float
    market_value: float
    sector: str
    asset_class: str
    dividend_yield: float


class PortfolioAnalysis(BaseModel):
    total_market_value: float
    total_cost_basis: float
    unrealized_gain_loss: float
    asset_allocation: dict[str, float]
    sector_exposure: dict[str, float]
    weighted_dividend_yield: float
    risk_profile: str
    holdings: list[HoldingAnalysis]
