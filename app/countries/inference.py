"""Rule-based (offline) country inference from tickers, exchanges and currencies.

Deliberately makes no network calls, so inference is fast, deterministic and testable;
live yfinance metadata can be fed in through the `exchange`/`currency` fields when known.
"""

import re

from app.countries.registry import get_country, list_countries
from app.schemas.country import (
    Confidence,
    CountryBreakdownEntry,
    CountryResolution,
    HoldingCountryInference,
    HoldingCountryInput,
    PortfolioCountryInference,
)

US_CODE = "US"
_US_STYLE_TICKER = re.compile(r"^[A-Z]{1,5}$")
_US_SHARE_CLASS = re.compile(r"^[A-Z]{1,5}[.-][A-Z]$")  # BRK.B / BRK-B
_CONFIDENCE_RANK: dict[str, int] = {"low": 0, "medium": 1, "high": 2}
MIXED_DOMINANT_WEIGHT = 0.75


class CountryRequiredError(ValueError):
    """Raised when no country can be determined and the user must select one."""


def _lowest(*confidences: Confidence) -> Confidence:
    return min(confidences, key=lambda c: _CONFIDENCE_RANK[c])


def infer_holding_country(holding: HoldingCountryInput) -> HoldingCountryInference:
    ticker = holding.ticker.strip()
    upper = ticker.upper()
    countries = list_countries()

    suffix_country = next((c for c in countries if c.matches_suffix(upper)), None)
    exchange_country = (
        next((c for c in countries if c.matches_exchange(holding.exchange)), None) if holding.exchange else None
    )
    currency_country = (
        next((c for c in countries if c.matches_currency(holding.currency)), None) if holding.currency else None
    )

    def result(country: str | None, confidence: Confidence, reason: str) -> HoldingCountryInference:
        return HoldingCountryInference(ticker=ticker, country=country, confidence=confidence, reason=reason)

    if suffix_country:
        conflicts = sorted(
            {c.code for c in (exchange_country, currency_country) if c and c.code != suffix_country.code}
        )
        if conflicts:
            return result(
                suffix_country.code,
                "low",
                f"Ticker suffix indicates {suffix_country.code} but exchange/currency indicates {', '.join(conflicts)}",
            )
        return result(suffix_country.code, "high", f"Ticker suffix matches {suffix_country.name} listing")

    if exchange_country:
        return result(exchange_country.code, "high", f"Exchange '{holding.exchange}' is a {exchange_country.name} venue")

    if "." in upper and not _US_SHARE_CLASS.match(upper):
        suffix = upper[upper.rindex(".") :]
        if currency_country:
            return result(
                currency_country.code,
                "low",
                f"Unrecognised suffix '{suffix}'; currency suggests {currency_country.name}",
            )
        return result(None, "low", f"Unrecognised exchange suffix '{suffix}'")

    if currency_country:
        return result(currency_country.code, "medium", f"Quote currency {holding.currency} suggests {currency_country.name}")

    if _US_STYLE_TICKER.match(upper) or _US_SHARE_CLASS.match(upper):
        return result(US_CODE, "medium", "No exchange suffix; assumed a US listing")

    return result(None, "low", "Ticker format does not match any supported market")


def infer_portfolio_country(holdings: list[HoldingCountryInput]) -> PortfolioCountryInference:
    per_holding = [infer_holding_country(h) for h in holdings]
    use_values = bool(holdings) and all(h.market_value is not None and h.market_value > 0 for h in holdings)
    raw_weights = [h.market_value if use_values else 1.0 for h in holdings]
    weighting = "market_value" if use_values else "holding_count"

    by_country: dict[str, tuple[float, list[str]]] = {}
    for inference, weight in zip(per_holding, raw_weights):
        if inference.country is None:
            continue
        total_weight, tickers = by_country.get(inference.country, (0.0, []))
        by_country[inference.country] = (total_weight + weight, tickers + [inference.ticker])

    unresolved = [p.ticker for p in per_holding if p.country is None]

    if not by_country:
        return PortfolioCountryInference(
            inferred_country=None,
            confidence="low",
            is_mixed=False,
            weighting=weighting,
            breakdown=[],
            unresolved_tickers=unresolved,
            holdings=per_holding,
        )

    resolved_total = sum(weight for weight, _ in by_country.values())
    breakdown = sorted(
        (
            CountryBreakdownEntry(country=code, weight=weight / resolved_total, tickers=tickers)
            for code, (weight, tickers) in by_country.items()
        ),
        key=lambda e: (-e.weight, -len(e.tickers), e.country),
    )
    primary = breakdown[0]
    is_mixed = len(breakdown) > 1

    confidence = _lowest(*(p.confidence for p in per_holding if p.country))
    if is_mixed:
        confidence = _lowest(confidence, "medium" if primary.weight >= MIXED_DOMINANT_WEIGHT else "low")
    if unresolved:
        confidence = "low"

    return PortfolioCountryInference(
        inferred_country=primary.country,
        confidence=confidence,
        is_mixed=is_mixed,
        weighting=weighting,
        breakdown=breakdown,
        unresolved_tickers=unresolved,
        holdings=per_holding,
    )


def resolve_country(holdings: list[HoldingCountryInput], selected_country: str | None) -> CountryResolution:
    """A user-selected country always wins; otherwise fall back to inference."""
    inference = infer_portfolio_country(holdings) if holdings else None

    if selected_country:
        return CountryResolution(
            effective_country=get_country(selected_country).code,
            source="user_selected",
            inference=inference,
        )
    if inference and inference.inferred_country:
        return CountryResolution(effective_country=inference.inferred_country, source="inferred", inference=inference)
    if not holdings:
        raise CountryRequiredError("No portfolio provided; please select a country.")
    raise CountryRequiredError(
        f"Could not infer a country from the portfolio (unrecognised: {', '.join(inference.unresolved_tickers)}); "
        "please select a country."
    )
