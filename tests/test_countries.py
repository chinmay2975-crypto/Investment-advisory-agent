import pytest

from app.countries import (
    CountryRequiredError,
    UnknownCountryError,
    get_country,
    infer_holding_country,
    infer_portfolio_country,
    list_countries,
    resolve_country,
)
from app.schemas.country import HoldingCountryInput


def h(ticker, **kwargs) -> HoldingCountryInput:
    return HoldingCountryInput(ticker=ticker, **kwargs)


# --- country config -------------------------------------------------------------------


def test_registry_contains_india_us_uk():
    assert {c.code for c in list_countries()} == {"IN", "US", "GB"}


@pytest.mark.parametrize("code", ["UK", "uk", "GB", " gb "])
def test_uk_alias_and_case_insensitive_lookup(code):
    assert get_country(code).code == "GB"


def test_unknown_country_raises():
    with pytest.raises(UnknownCountryError):
        get_country("FR")


@pytest.mark.parametrize(
    "code, currency, benchmark",
    [("IN", "INR", "^NSEI"), ("US", "USD", "^GSPC"), ("GB", "GBP", "^FTSE")],
)
def test_country_core_fields(code, currency, benchmark):
    country = get_country(code)
    assert country.currency == currency
    assert country.benchmark_ticker == benchmark


@pytest.mark.parametrize("country", list_countries(), ids=lambda c: c.code)
def test_every_country_config_is_complete(country):
    assert 0 < country.risk_free_rate.fallback_rate < 0.2
    assert country.risk_free_rate.fred_series
    assert country.capital_gains_tax.summary
    assert "general information" in country.capital_gains_tax.notice.lower()
    assert country.tax_advantaged_accounts
    assert "general information" in country.regulatory_disclaimer.lower()


def test_uk_prices_in_pence_are_converted_to_pounds():
    uk = get_country("GB")
    assert uk.to_major_units(1250.0, "GBp") == 12.5
    assert uk.to_major_units(12.5, "GBP") == 12.5


def test_short_term_holding_rules_differ_by_country():
    assert get_country("IN").capital_gains_tax.short_term_holding_months == 12
    assert get_country("US").capital_gains_tax.short_term_holding_months == 12
    assert get_country("GB").capital_gains_tax.short_term_holding_months is None


# --- single-holding inference -------------------------------------------------------


@pytest.mark.parametrize(
    "ticker, country, confidence",
    [
        ("RELIANCE.NS", "IN", "high"),
        ("TCS.BO", "IN", "high"),
        ("infy.ns", "IN", "high"),
        ("VOD.L", "GB", "high"),
        ("AAPL", "US", "medium"),
        ("BRK-B", "US", "medium"),
        ("BRK.B", "US", "medium"),
        ("SHOP.TO", None, "low"),
        ("RELIANCE", None, "low"),  # too long for a US ticker, no suffix: genuinely ambiguous
    ],
)
def test_infer_from_ticker_alone(ticker, country, confidence):
    result = infer_holding_country(h(ticker))
    assert (result.country, result.confidence) == (country, confidence)


def test_exchange_resolves_unsuffixed_ticker():
    result = infer_holding_country(h("RELIANCE", exchange="NSI"))
    assert (result.country, result.confidence) == ("IN", "high")


def test_currency_resolves_unsuffixed_ticker_with_medium_confidence():
    result = infer_holding_country(h("RELIANCE", currency="INR"))
    assert (result.country, result.confidence) == ("IN", "medium")


def test_minor_currency_unit_gbp_pence_recognised():
    result = infer_holding_country(h("BARC", currency="GBp"))
    assert result.country == "GB"


def test_suffix_conflicting_with_exchange_lowers_confidence():
    result = infer_holding_country(h("VOD.L", exchange="NYQ"))
    assert result.country == "GB"
    assert result.confidence == "low"
    assert "US" in result.reason


# --- portfolio inference --------------------------------------------------------------


def test_all_indian_portfolio_is_high_confidence():
    result = infer_portfolio_country([h("RELIANCE.NS"), h("TCS.NS"), h("HDFCBANK.BO")])
    assert result.inferred_country == "IN"
    assert result.confidence == "high"
    assert not result.is_mixed
    assert result.breakdown[0].weight == pytest.approx(1.0)


def test_all_unsuffixed_us_portfolio_is_medium_confidence():
    result = infer_portfolio_country([h("AAPL"), h("MSFT"), h("VTI")])
    assert result.inferred_country == "US"
    assert result.confidence == "medium"


def test_mixed_portfolio_weighted_by_market_value():
    holdings = [
        h("RELIANCE.NS", market_value=60_000),
        h("AAPL", market_value=30_000),
        h("VOD.L", market_value=10_000),
    ]
    result = infer_portfolio_country(holdings)

    assert result.is_mixed
    assert result.weighting == "market_value"
    assert result.inferred_country == "IN"
    weights = {e.country: e.weight for e in result.breakdown}
    assert weights == pytest.approx({"IN": 0.6, "US": 0.3, "GB": 0.1})
    assert sum(weights.values()) == pytest.approx(1.0)
    assert result.confidence == "low"  # dominant country under 75%


def test_mixed_portfolio_with_dominant_country_is_medium_confidence():
    holdings = [h("RELIANCE.NS", market_value=90), h("TCS.NS", market_value=5), h("VOD.L", market_value=5)]
    result = infer_portfolio_country(holdings)
    assert result.is_mixed
    assert result.inferred_country == "IN"
    assert result.confidence == "medium"


def test_falls_back_to_holding_count_when_any_value_missing():
    result = infer_portfolio_country([h("RELIANCE.NS", market_value=1_000_000), h("AAPL"), h("MSFT")])
    assert result.weighting == "holding_count"
    assert result.inferred_country == "US"


def test_even_split_tie_is_deterministic_and_low_confidence():
    result = infer_portfolio_country([h("RELIANCE.NS"), h("AAPL")])
    assert result.is_mixed
    assert result.confidence == "low"
    assert result.inferred_country == infer_portfolio_country([h("AAPL"), h("RELIANCE.NS")]).inferred_country


def test_unresolved_tickers_reported_and_force_low_confidence():
    result = infer_portfolio_country([h("RELIANCE.NS"), h("SHOP.TO")])
    assert result.inferred_country == "IN"
    assert result.unresolved_tickers == ["SHOP.TO"]
    assert result.confidence == "low"


def test_fully_ambiguous_portfolio_has_no_inferred_country():
    result = infer_portfolio_country([h("SHOP.TO"), h("RELIANCE")])
    assert result.inferred_country is None
    assert result.breakdown == []


# --- resolution (inference vs user selection) ------------------------------------------


def test_user_selection_overrides_inference():
    resolution = resolve_country([h("RELIANCE.NS")], selected_country="uk")
    assert resolution.effective_country == "GB"
    assert resolution.source == "user_selected"
    assert resolution.inference.inferred_country == "IN"


def test_inferred_when_no_selection():
    resolution = resolve_country([h("VOD.L")], selected_country=None)
    assert (resolution.effective_country, resolution.source) == ("GB", "inferred")


def test_no_portfolio_requires_selected_country():
    with pytest.raises(CountryRequiredError):
        resolve_country([], selected_country=None)


def test_no_portfolio_with_selection_is_fine():
    resolution = resolve_country([], selected_country="IN")
    assert resolution.effective_country == "IN"
    assert resolution.inference is None


def test_ambiguous_portfolio_without_selection_requires_country():
    with pytest.raises(CountryRequiredError, match="SHOP.TO"):
        resolve_country([h("SHOP.TO")], selected_country=None)


def test_invalid_selected_country_raises():
    with pytest.raises(UnknownCountryError):
        resolve_country([h("AAPL")], selected_country="FR")
