from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["high", "medium", "low"]


class HoldingCountryInput(BaseModel):
    ticker: str = Field(examples=["RELIANCE.NS"])
    exchange: str | None = Field(default=None, examples=["NSI"])
    currency: str | None = Field(default=None, examples=["INR"])
    # Optional weighting; must be in one common currency across holdings to be meaningful.
    market_value: float | None = Field(default=None, examples=[250000.0])


class HoldingCountryInference(BaseModel):
    ticker: str
    country: str | None
    confidence: Confidence
    reason: str


class CountryBreakdownEntry(BaseModel):
    country: str
    weight: float  # share of the *resolved* portion of the portfolio, 0-1
    tickers: list[str]


class PortfolioCountryInference(BaseModel):
    inferred_country: str | None
    confidence: Confidence
    is_mixed: bool
    weighting: Literal["market_value", "holding_count"]
    breakdown: list[CountryBreakdownEntry]
    unresolved_tickers: list[str]
    holdings: list[HoldingCountryInference]


class CountryResolution(BaseModel):
    effective_country: str
    source: Literal["inferred", "user_selected"]
    inference: PortfolioCountryInference | None
