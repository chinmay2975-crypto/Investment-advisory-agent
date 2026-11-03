from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.country import CountryResolution, HoldingCountryInput

Lookback = Literal["6mo", "1y", "2y", "5y"]


class TaxNotes(BaseModel):
    as_of: str
    short_term_holding_months: int | None
    summary: list[str]
    notice: str


class AccountInfo(BaseModel):
    name: str
    summary: str


class CountryOut(BaseModel):
    code: str
    name: str
    currency: str
    currency_symbol: str
    benchmark_ticker: str
    benchmark_name: str
    risk_free_rate_label: str
    risk_free_rate_fallback: float
    ticker_suffixes: list[str]
    exchanges: list[str]
    capital_gains_tax: TaxNotes
    tax_advantaged_accounts: list[AccountInfo]
    regulatory_disclaimer: str


class CountryInferRequest(BaseModel):
    holdings: list[HoldingCountryInput]

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "holdings": [
                        {"ticker": "RELIANCE.NS", "market_value": 60000},
                        {"ticker": "AAPL", "market_value": 30000},
                        {"ticker": "VOD.L", "market_value": 10000},
                    ]
                }
            ]
        }
    )


class PortfolioHoldingIn(BaseModel):
    ticker: str = Field(min_length=1, max_length=24)
    quantity: float = Field(gt=0)
    cost_basis: float | None = Field(default=None, ge=0, description="Per-unit cost in the holding's own currency")
    exchange: str | None = None
    currency: str | None = None


class PortfolioAnalyzeRequest(BaseModel):
    holdings: list[PortfolioHoldingIn] = Field(default_factory=list)
    country: str | None = Field(default=None, description="Override; inferred from holdings when omitted")
    base_currency: str | None = Field(
        default=None, description="Currency for the combined view; defaults to the effective country's currency"
    )
    lookback: Lookback = "1y"

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "holdings": [
                        {"ticker": "RELIANCE.NS", "quantity": 20, "cost_basis": 2400},
                        {"ticker": "INFY.NS", "quantity": 30, "cost_basis": 1450},
                        {"ticker": "AAPL", "quantity": 5, "cost_basis": 180},
                    ],
                    "country": None,
                    "base_currency": "INR",
                    "lookback": "1y",
                },
                {
                    "holdings": [{"ticker": "VOD.L", "quantity": 1000}, {"ticker": "HSBA.L", "quantity": 200}],
                    "country": "UK",
                    "base_currency": "GBP",
                    "lookback": "1y",
                },
            ]
        }
    )


class RiskFreeRateInfo(BaseModel):
    country: str
    label: str
    rate: float
    source: Literal["live", "fallback"]


class RiskMetrics(BaseModel):
    currency: str
    benchmark_ticker: str
    benchmark_name: str
    observations: int
    total_return: float | None
    annualized_return: float | None
    annualized_volatility: float | None
    sharpe_ratio: float | None
    beta: float | None
    max_drawdown: float | None
    benchmark_total_return: float | None
    risk_free_rate: RiskFreeRateInfo


class AnalyzedHolding(BaseModel):
    ticker: str
    name: str | None
    country: str
    country_confidence: Literal["high", "medium", "low"]
    currency: str
    quantity: float
    price: float | None  # latest price in the holding's major currency
    value_local: float | None
    value_base: float | None
    weight: float  # share of total value in base currency
    sector: str
    asset_class: str
    cost_basis: float | None
    unrealized_gain_local: float | None


class CountryAnalysis(BaseModel):
    country: str
    name: str
    currency: str
    weight: float
    value_local: float
    value_base: float
    tickers: list[str]
    metrics: RiskMetrics | None


class Concentration(BaseModel):
    hhi: float
    effective_holdings: float
    largest_position_ticker: str
    largest_position_weight: float


class PerformancePoint(BaseModel):
    date: date
    portfolio: float
    benchmark: float | None


class PortfolioAnalyzeResponse(BaseModel):
    country: CountryResolution
    country_name: str
    base_currency: str
    lookback: Lookback
    as_of: date
    total_value_base: float
    holdings: list[AnalyzedHolding]
    allocation_by_country: dict[str, float]
    allocation_by_sector: dict[str, float]
    allocation_by_asset_class: dict[str, float]
    currency_exposure: dict[str, float]
    combined_metrics: RiskMetrics | None
    per_country: list[CountryAnalysis]
    concentration: Concentration | None
    performance: list[PerformancePoint]
    tax_notes: TaxNotes
    tax_advantaged_accounts: list[AccountInfo]
    regulatory_disclaimer: str
    warnings: list[str]
