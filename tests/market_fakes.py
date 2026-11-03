"""Synthetic market data for country-aware analysis tests (no network)."""

import numpy as np
import pandas as pd

from app.services import price_data
from app.services.price_data import PriceHistory, RiskFreeRate

DATES = pd.bdate_range("2025-01-01", periods=260)


def series(start: float, drift: float = 0.0005, seed: int = 0, scale: float = 1.0) -> pd.Series:
    rng = np.random.default_rng(seed)
    returns = drift + rng.normal(0, 0.01, len(DATES)) * scale
    return pd.Series(start * np.cumprod(1 + returns), index=DATES)


def constant(value: float) -> pd.Series:
    return pd.Series(value, index=DATES, dtype=float)


DEFAULT_PRICES = {
    "RELIANCE.NS": (series(2500, seed=1), "INR"),
    "TCS.NS": (series(3800, seed=2), "INR"),
    "AAPL": (series(190, seed=3), "USD"),
    "MSFT": (series(410, seed=4), "USD"),
    "VOD.L": (constant(100.0), "GBp"),  # 100 pence = £1.00
    "^NSEI": (series(22000, seed=1), "INR"),  # same seed as RELIANCE -> perfectly correlated
    "^GSPC": (series(5000, seed=3), "USD"),
    "^FTSE": (series(8000, seed=5), "GBP"),
    "USDINR=X": (constant(80.0), None),
    "GBPINR=X": (constant(100.0), None),
    "INRUSD=X": (constant(1 / 80.0), None),
    "GBPUSD=X": (constant(1.25), None),
    "INRGBP=X": (constant(0.01), None),
    "USDGBP=X": (constant(0.8), None),
}

DEFAULT_METADATA = {
    "RELIANCE.NS": {"name": "Reliance", "sector": "Energy", "quote_type": "EQUITY"},
    "TCS.NS": {"name": "TCS", "sector": "Technology", "quote_type": "EQUITY"},
    "AAPL": {"name": "Apple", "sector": "Technology", "quote_type": "EQUITY"},
    "MSFT": {"name": "Microsoft", "sector": "Technology", "quote_type": "EQUITY"},
    "VOD.L": {"name": "Vodafone", "sector": "Communication Services", "quote_type": "EQUITY"},
}

RISK_FREE = {"IN": 0.07, "US": 0.04, "GB": 0.045}


def install(monkeypatch, prices: dict | None = None, metadata: dict | None = None):
    prices = {**DEFAULT_PRICES, **(prices or {})}
    metadata = {**DEFAULT_METADATA, **(metadata or {})}

    def fake_history(ticker: str, period: str) -> PriceHistory:
        closes, currency = prices.get(ticker.upper(), (pd.Series(dtype=float), None))
        return PriceHistory(closes=closes, currency=currency)

    monkeypatch.setattr(price_data, "fetch_price_history", fake_history)
    monkeypatch.setattr(price_data, "fetch_ticker_metadata", lambda t: metadata.get(t.upper(), {}))
    monkeypatch.setattr(
        price_data, "fetch_risk_free_rate", lambda country: RiskFreeRate(rate=RISK_FREE[country.code], source="fallback")
    )
