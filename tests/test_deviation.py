from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pandas as pd

from app.services.deviation import compute_deviation


class FakeTicker:
    def __init__(self, start_price, end_price):
        self.start_price = start_price
        self.end_price = end_price

    def history(self, **kwargs):
        if "start" in kwargs:
            return pd.DataFrame({"Close": [self.start_price]})
        return pd.DataFrame({"Close": [self.end_price]})


class EmptyTicker:
    def history(self, **kwargs):
        return pd.DataFrame()


def test_compute_deviation_averages_returns_across_instruments():
    generated_at = datetime.now(timezone.utc) - timedelta(days=60)
    payload = {"suggested_instruments": ["VTI", "BND"]}

    fakes = {"VTI": FakeTicker(100.0, 110.0), "BND": FakeTicker(50.0, 49.0)}

    with patch("app.services.deviation.yf.Ticker", side_effect=lambda t: fakes[t]):
        result = compute_deviation(payload, generated_at)

    assert result["elapsed_days"] == 60
    assert result["per_instrument"]["VTI"] == 10.0
    assert result["per_instrument"]["BND"] == -2.0
    assert result["realized_return_pct"] == 4.0


def test_compute_deviation_skips_instruments_with_no_price_history():
    generated_at = datetime.now(timezone.utc) - timedelta(days=30)
    payload = {"suggested_instruments": ["MISSING"]}

    with patch("app.services.deviation.yf.Ticker", return_value=EmptyTicker()):
        result = compute_deviation(payload, generated_at)

    assert result["per_instrument"] == {}
    assert result["realized_return_pct"] == 0.0


def test_compute_deviation_handles_no_instruments():
    generated_at = datetime.now(timezone.utc) - timedelta(days=10)
    result = compute_deviation({"suggested_instruments": []}, generated_at)
    assert result["realized_return_pct"] == 0.0
    assert result["per_instrument"] == {}
