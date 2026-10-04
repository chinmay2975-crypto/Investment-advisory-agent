from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.db.models import Holding
from app.services.tax_calculator import analyze_tax, classify_holding_period, long_term_capital_gains_rate


def test_long_term_capital_gains_rate_brackets():
    assert long_term_capital_gains_rate(30000, "single") == 0.0
    assert long_term_capital_gains_rate(100000, "single") == 0.15
    assert long_term_capital_gains_rate(1000000, "single") == 0.20


def test_classify_holding_period():
    now = datetime.now(timezone.utc)
    assert classify_holding_period(now - timedelta(days=400), as_of=now) == "long_term"
    assert classify_holding_period(now - timedelta(days=30), as_of=now) == "short_term"
    assert classify_holding_period(None) == "unknown"


def test_analyze_tax_computes_short_and_long_term_gains():
    now = datetime.now(timezone.utc)
    holdings = [
        Holding(
            investor_id=1,
            ticker="VTI",
            quantity=10,
            cost_basis=150.0,
            acquired_at=now - timedelta(days=400),
            source="manual",
        ),
        Holding(
            investor_id=1,
            ticker="BND",
            quantity=20,
            cost_basis=75.0,
            acquired_at=now - timedelta(days=30),
            source="manual",
        ),
    ]

    def fake_info(ticker):
        return {"currentPrice": 200.0} if ticker == "VTI" else {"currentPrice": 70.0}

    with patch("app.services.portfolio_analysis.yf.Ticker") as mock_ticker:
        mock_ticker.side_effect = lambda t: type("T", (), {"info": fake_info(t)})()
        result = analyze_tax(
            holdings, ordinary_income_tax_rate=0.24, taxable_income=100000, filing_status="single"
        )

    vti_detail = next(d for d in result["holdings"] if d["ticker"] == "VTI")
    bnd_detail = next(d for d in result["holdings"] if d["ticker"] == "BND")

    assert vti_detail["holding_period"] == "long_term"
    assert vti_detail["unrealized_gain"] == (200.0 - 150.0) * 10
    assert vti_detail["estimated_tax_rate"] == 0.15
    assert vti_detail["estimated_tax"] == vti_detail["unrealized_gain"] * 0.15

    assert bnd_detail["holding_period"] == "short_term"
    assert bnd_detail["unrealized_gain"] == (70.0 - 75.0) * 20
    assert bnd_detail["estimated_tax_rate"] == 0.24
    # unrealized loss -> no tax owed on this holding
    assert bnd_detail["estimated_tax"] == 0.0


def test_analyze_tax_skips_holdings_without_cost_basis_or_acquired_at():
    holdings = [Holding(investor_id=1, ticker="VTI", quantity=10, source="manual")]

    with patch("app.services.portfolio_analysis.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.info = {"currentPrice": 200.0}
        result = analyze_tax(holdings, ordinary_income_tax_rate=0.24, taxable_income=100000)

    detail = result["holdings"][0]
    assert detail["holding_period"] == "unknown"
    assert detail["estimated_tax"] == 0.0
