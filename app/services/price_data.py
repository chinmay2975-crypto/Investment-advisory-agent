"""yfinance/FRED data access for country-aware portfolio analysis.

Every network call goes through one of the public functions below so tests can patch them,
and results are cached per calendar day (prices only change daily for this analysis).
"""

from dataclasses import dataclass
from datetime import date
from functools import lru_cache

import pandas as pd
import yfinance as yf

from app.config import settings
from app.countries.base import CountryConfig
from app.services.macro_data import _fetch_latest_observation


@dataclass(frozen=True)
class PriceHistory:
    closes: pd.Series  # adjusted closes in the quote currency, tz-naive daily DatetimeIndex
    currency: str | None


@dataclass(frozen=True)
class RiskFreeRate:
    rate: float  # annual decimal
    source: str  # "live" or "fallback"


def _today() -> str:
    return date.today().isoformat()


def _to_daily_series(history: pd.DataFrame) -> pd.Series:
    if history is None or history.empty or "Close" not in history:
        return pd.Series(dtype=float)
    closes = history["Close"].astype(float)
    closes.index = pd.to_datetime([ts.date() for ts in closes.index])
    return closes[~closes.index.duplicated(keep="last")].dropna()


@lru_cache(maxsize=512)
def _cached_price_history(ticker: str, period: str, _day: str) -> PriceHistory:
    yticker = yf.Ticker(ticker)
    try:
        history = yticker.history(period=period, auto_adjust=True)
    except Exception:
        history = pd.DataFrame()
    currency = None
    try:
        currency = yticker.fast_info["currency"]
    except Exception:
        pass
    return PriceHistory(closes=_to_daily_series(history), currency=currency)


def fetch_price_history(ticker: str, period: str) -> PriceHistory:
    return _cached_price_history(ticker.strip().upper(), period, _today())


@lru_cache(maxsize=256)
def _cached_metadata(ticker: str, _day: str) -> dict:
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        info = {}
    return {
        "name": info.get("shortName") or info.get("longName"),
        "sector": info.get("sector"),
        "quote_type": info.get("quoteType"),
        "category": info.get("category"),
        "exchange": info.get("exchange"),
        "currency": info.get("currency"),
    }


def fetch_ticker_metadata(ticker: str) -> dict:
    return _cached_metadata(ticker.strip().upper(), _today())


def fetch_fx_history(from_currency: str, to_currency: str, period: str) -> pd.Series:
    """Daily rate to multiply a `from_currency` amount by to get `to_currency`."""
    if from_currency == to_currency:
        return pd.Series(dtype=float)
    return fetch_price_history(f"{from_currency}{to_currency}=X", period).closes


@lru_cache(maxsize=16)
def _cached_risk_free_rate(country_code: str, yfinance_ticker: str | None, fred_series: str, fallback: float, _day: str):
    if yfinance_ticker:
        closes = fetch_price_history(yfinance_ticker, "5d").closes
        if not closes.empty:
            return RiskFreeRate(rate=float(closes.iloc[-1]) / 100, source="live")
    if settings.fred_api_key:
        try:
            observation = _fetch_latest_observation(fred_series)
            if observation and observation.get("value") not in (None, "."):
                return RiskFreeRate(rate=float(observation["value"]) / 100, source="live")
        except Exception:
            pass
    return RiskFreeRate(rate=fallback, source="fallback")


def fetch_risk_free_rate(country: CountryConfig) -> RiskFreeRate:
    source = country.risk_free_rate
    return _cached_risk_free_rate(
        country.code, source.yfinance_ticker, source.fred_series, source.fallback_rate, _today()
    )
