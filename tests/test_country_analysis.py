import pandas as pd
import pytest

from app.countries import CountryRequiredError, UnknownCountryError
from app.schemas.analysis import PortfolioAnalyzeRequest, PortfolioHoldingIn
from app.services.country_analysis import UnsupportedCurrencyError, analyze_portfolio
from tests import market_fakes


@pytest.fixture(autouse=True)
def fake_market(monkeypatch):
    market_fakes.install(monkeypatch)


def request(holdings, **kwargs) -> PortfolioAnalyzeRequest:
    return PortfolioAnalyzeRequest(holdings=[PortfolioHoldingIn(**h) for h in holdings], **kwargs)


def test_single_country_portfolio_uses_local_benchmark_and_risk_free_rate():
    result = analyze_portfolio(request([{"ticker": "RELIANCE.NS", "quantity": 10}]))

    assert result.country.effective_country == "IN"
    assert result.country.source == "inferred"
    assert result.base_currency == "INR"
    metrics = result.combined_metrics
    assert metrics.benchmark_ticker == "^NSEI"
    assert metrics.risk_free_rate.rate == 0.07
    # RELIANCE and ^NSEI share a random seed, so returns are identical -> beta exactly 1
    assert metrics.beta == pytest.approx(1.0, abs=1e-6)
    assert metrics.total_return == pytest.approx(metrics.benchmark_total_return, abs=1e-6)
    assert metrics.max_drawdown <= 0
    assert metrics.sharpe_ratio is not None
    assert result.tax_notes.short_term_holding_months == 12
    assert "SEBI" in result.regulatory_disclaimer


def test_mixed_portfolio_converts_to_base_currency_and_splits_by_country():
    result = analyze_portfolio(
        request(
            [{"ticker": "RELIANCE.NS", "quantity": 10}, {"ticker": "AAPL", "quantity": 10}],
            base_currency="INR",
        )
    )
    holdings = {h.ticker: h for h in result.holdings}
    aapl = holdings["AAPL"]

    assert aapl.currency == "USD"
    assert aapl.value_base == pytest.approx(aapl.value_local * 80, rel=1e-6)
    assert result.total_value_base == pytest.approx(sum(h.value_base for h in result.holdings), rel=1e-6)
    assert sum(result.allocation_by_country.values()) == pytest.approx(1.0)
    assert set(result.currency_exposure) == {"INR", "USD"}

    per_country = {c.country: c for c in result.per_country}
    assert per_country["US"].currency == "USD"
    assert per_country["US"].metrics.benchmark_ticker == "^GSPC"
    assert per_country["US"].metrics.risk_free_rate.country == "US"
    assert per_country["IN"].metrics.benchmark_ticker == "^NSEI"
    # combined view is measured against the base currency's country
    assert result.combined_metrics.benchmark_ticker == "^NSEI"
    assert result.country.inference.is_mixed


def test_base_currency_selects_combined_benchmark():
    result = analyze_portfolio(
        request([{"ticker": "RELIANCE.NS", "quantity": 10}, {"ticker": "AAPL", "quantity": 10}], base_currency="USD")
    )
    assert result.combined_metrics.benchmark_ticker == "^GSPC"
    assert result.combined_metrics.currency == "USD"


def test_uk_prices_quoted_in_pence_are_converted():
    result = analyze_portfolio(request([{"ticker": "VOD.L", "quantity": 1000}]))
    vod = result.holdings[0]
    assert result.country.effective_country == "GB"
    assert vod.currency == "GBP"
    assert vod.price == pytest.approx(1.0)
    assert result.total_value_base == pytest.approx(1000.0)


def test_value_weighted_inference_can_change_default_base_currency():
    # count-weighted: 2 US vs 1 IN; value-weighted: IN dominates -> analysis re-runs in INR
    result = analyze_portfolio(
        request(
            [
                {"ticker": "AAPL", "quantity": 1},
                {"ticker": "MSFT", "quantity": 1},
                {"ticker": "RELIANCE.NS", "quantity": 1000},
            ]
        )
    )
    assert result.country.effective_country == "IN"
    assert result.base_currency == "INR"


def test_country_override_with_no_holdings_returns_country_context():
    result = analyze_portfolio(request([], country="UK"))
    assert result.country.effective_country == "GB"
    assert result.country.source == "user_selected"
    assert result.base_currency == "GBP"
    assert result.holdings == []
    assert result.combined_metrics is None
    assert "FCA" in result.regulatory_disclaimer


def test_no_holdings_and_no_country_requires_selection():
    with pytest.raises(CountryRequiredError):
        analyze_portfolio(request([]))


def test_unknown_country_and_currency_rejected():
    with pytest.raises(UnknownCountryError):
        analyze_portfolio(request([{"ticker": "AAPL", "quantity": 1}], country="FR"))
    with pytest.raises(UnsupportedCurrencyError):
        analyze_portfolio(request([{"ticker": "AAPL", "quantity": 1}], base_currency="EUR"))


def test_missing_price_history_is_reported_not_fatal():
    result = analyze_portfolio(request([{"ticker": "AAPL", "quantity": 1}, {"ticker": "NOPE", "quantity": 5}]))
    assert any("NOPE" in w for w in result.warnings)
    assert [h.ticker for h in result.holdings if h.value_base] == ["AAPL"]


def test_concentration_and_duplicate_tickers():
    result = analyze_portfolio(
        request(
            [
                {"ticker": "AAPL", "quantity": 5, "cost_basis": 100},
                {"ticker": "aapl", "quantity": 5, "cost_basis": 200},
                {"ticker": "MSFT", "quantity": 1},
            ]
        )
    )
    aapl = next(h for h in result.holdings if h.ticker == "AAPL")
    assert aapl.quantity == 10
    assert aapl.cost_basis == pytest.approx(150)
    assert 0 < result.concentration.hhi <= 1
    assert result.concentration.effective_holdings == pytest.approx(1 / result.concentration.hhi, rel=1e-3)
    assert result.concentration.largest_position_ticker == "AAPL"


def test_short_history_gives_null_metrics_with_warning(monkeypatch):
    short = pd.Series([10.0, 10.5, 10.2], index=market_fakes.DATES[:3])
    market_fakes.install(monkeypatch, prices={"AAPL": (short, "USD")})
    result = analyze_portfolio(request([{"ticker": "AAPL", "quantity": 1}]))
    assert result.combined_metrics.total_return is None
    assert any("Not enough price history" in w for w in result.warnings)


def test_performance_series_starts_at_100():
    result = analyze_portfolio(request([{"ticker": "MSFT", "quantity": 3}]))
    assert result.performance[0].portfolio == pytest.approx(100.0)
    assert result.performance[0].benchmark == pytest.approx(100.0)
    assert len(result.performance) <= 70
