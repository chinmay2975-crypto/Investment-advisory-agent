from unittest.mock import patch

from app.db.models import Holding
from app.services.portfolio_analysis import analyze_portfolio


def _holding(ticker, quantity, cost_basis=None):
    return Holding(investor_id=1, ticker=ticker, quantity=quantity, cost_basis=cost_basis, source="manual")


def test_analyze_portfolio_returns_empty_summary_for_no_holdings():
    result = analyze_portfolio([])
    assert result["total_market_value"] == 0.0
    assert result["risk_profile"] == "Unknown"
    assert result["holdings"] == []


def test_analyze_portfolio_computes_allocation_sector_and_risk_profile():
    holdings = [_holding("VTI", 10, cost_basis=180.0), _holding("BND", 20, cost_basis=70.0)]

    def fake_info(ticker):
        if ticker == "VTI":
            return {
                "currentPrice": 200.0,
                "quoteType": "ETF",
                "category": "Large Blend",
                "sector": "Diversified",
                "dividendYield": 0.015,
            }
        return {
            "currentPrice": 72.0,
            "quoteType": "ETF",
            "category": "Intermediate Core Bond",
            "sector": "Fixed Income",
            "dividendYield": 0.03,
        }

    with patch("app.services.portfolio_analysis.yf.Ticker") as mock_ticker:
        mock_ticker.side_effect = lambda t: type("T", (), {"info": fake_info(t)})()
        result = analyze_portfolio(holdings)

    assert result["total_market_value"] == 10 * 200.0 + 20 * 72.0
    assert result["total_cost_basis"] == 10 * 180.0 + 20 * 70.0
    assert result["asset_allocation"]["stocks"] > 0
    assert result["asset_allocation"]["bonds"] > 0
    assert "Diversified" in result["sector_exposure"]
    assert "Fixed Income" in result["sector_exposure"]
    assert result["risk_profile"] in {"Conservative", "Balanced", "Aggressive"}
    assert len(result["holdings"]) == 2


def test_analyze_portfolio_classifies_bond_category_even_for_etf_quote_type():
    holdings = [_holding("BND", 5)]

    fake_info = {
        "currentPrice": 70.0,
        "quoteType": "ETF",
        "category": "Long-Term Bond",
        "sector": "Fixed Income",
        "dividendYield": 0.03,
    }

    with patch("app.services.portfolio_analysis.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.info = fake_info
        result = analyze_portfolio(holdings)

    assert result["asset_allocation"] == {"bonds": 100.0}
    assert result["risk_profile"] == "Conservative"
