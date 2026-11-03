from fastapi import APIRouter

from app.countries import infer_portfolio_country, list_countries
from app.countries.base import CountryConfig
from app.schemas.analysis import CountryInferRequest, CountryOut
from app.schemas.country import PortfolioCountryInference
from app.services.country_analysis import accounts_for, tax_notes_for

router = APIRouter(prefix="/countries", tags=["countries"])


def country_out(country: CountryConfig) -> CountryOut:
    return CountryOut(
        code=country.code,
        name=country.name,
        currency=country.currency,
        currency_symbol=country.currency_symbol,
        benchmark_ticker=country.benchmark_ticker,
        benchmark_name=country.benchmark_name,
        risk_free_rate_label=country.risk_free_rate.label,
        risk_free_rate_fallback=country.risk_free_rate.fallback_rate,
        ticker_suffixes=list(country.ticker_suffixes),
        exchanges=list(country.exchanges),
        capital_gains_tax=tax_notes_for(country),
        tax_advantaged_accounts=accounts_for(country),
        regulatory_disclaimer=country.regulatory_disclaimer,
    )


@router.get("", response_model=list[CountryOut], summary="List supported countries and their market conventions")
def get_countries():
    return [country_out(c) for c in list_countries()]


@router.post(
    "/infer",
    response_model=PortfolioCountryInference,
    summary="Infer the country of a portfolio from its tickers (no market data calls)",
)
def infer_country(payload: CountryInferRequest):
    return infer_portfolio_country(payload.holdings)
