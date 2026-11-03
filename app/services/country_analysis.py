"""Country-aware portfolio analysis.

All country-specific behaviour (benchmark, risk-free rate, currency, tax notes) comes from
`CountryConfig`; this module never branches on a specific country.

Combined view: values converted to the base currency, measured against the benchmark and
risk-free rate of the base currency's country. Per-country view: each country's holdings in
that country's currency, against its local benchmark and risk-free rate.
"""

import math
from datetime import date

import pandas as pd

from app.countries import get_country, infer_holding_country, list_countries, resolve_country
from app.countries.base import CountryConfig
from app.schemas.analysis import (
    AccountInfo,
    AnalyzedHolding,
    Concentration,
    CountryAnalysis,
    PerformancePoint,
    PortfolioAnalyzeRequest,
    PortfolioHoldingIn,
    PortfolioAnalyzeResponse,
    RiskFreeRateInfo,
    RiskMetrics,
    TaxNotes,
)
from app.schemas.country import HoldingCountryInput
from app.services import price_data
from app.services.portfolio_analysis import _classify_asset_class

TRADING_DAYS = 252
MIN_OBSERVATIONS = 20
PERFORMANCE_POINTS = 60


class UnsupportedCurrencyError(ValueError):
    pass


def _currency_countries() -> dict[str, CountryConfig]:
    return {c.currency: c for c in list_countries()}


def _major_currency(currency: str | None) -> tuple[str | None, int]:
    if not currency:
        return None, 1
    stripped = currency.strip()
    for country in list_countries():
        if stripped in country.minor_currency_units:
            return country.currency, country.minor_currency_units[stripped]
    return stripped.upper(), 1


def _num(value) -> float | None:
    if value is None:
        return None
    value = float(value)
    return None if math.isnan(value) or math.isinf(value) else round(value, 6)


def tax_notes_for(country: CountryConfig) -> TaxNotes:
    rules = country.capital_gains_tax
    return TaxNotes(
        as_of=rules.as_of,
        short_term_holding_months=rules.short_term_holding_months,
        summary=list(rules.summary),
        notice=rules.notice,
    )


def accounts_for(country: CountryConfig) -> list[AccountInfo]:
    return [AccountInfo(name=a.name, summary=a.summary) for a in country.tax_advantaged_accounts]


class _FxConverter:
    def __init__(self, lookback: str):
        self._lookback = lookback
        self._cache: dict[tuple[str, str], pd.Series | None] = {}

    def convert(self, series: pd.Series, from_currency: str, to_currency: str) -> pd.Series | None:
        if from_currency == to_currency:
            return series
        key = (from_currency, to_currency)
        if key not in self._cache:
            rates = price_data.fetch_fx_history(from_currency, to_currency, self._lookback)
            self._cache[key] = None if rates.empty else rates
        rates = self._cache[key]
        if rates is None:
            return None
        aligned = rates.reindex(rates.index.union(series.index)).sort_index().ffill().bfill().reindex(series.index)
        return series * aligned


def _metrics(values: pd.Series, benchmark: pd.Series, country: CountryConfig, currency: str) -> RiskMetrics:
    values = values.dropna()
    risk_free = price_data.fetch_risk_free_rate(country)
    common = {
        "currency": currency,
        "benchmark_ticker": country.benchmark_ticker,
        "benchmark_name": country.benchmark_name,
        "observations": len(values),
        "risk_free_rate": RiskFreeRateInfo(
            country=country.code,
            label=country.risk_free_rate.label,
            rate=risk_free.rate,
            source=risk_free.source,
        ),
    }
    empty = dict.fromkeys(
        (
            "total_return",
            "annualized_return",
            "annualized_volatility",
            "sharpe_ratio",
            "beta",
            "max_drawdown",
            "benchmark_total_return",
        )
    )
    if len(values) < MIN_OBSERVATIONS:
        return RiskMetrics(**common, **empty)

    returns = values.pct_change().dropna()
    total_return = values.iloc[-1] / values.iloc[0] - 1
    years = (values.index[-1] - values.index[0]).days / 365.25
    annualized = (1 + total_return) ** (1 / years) - 1 if years > 0 and total_return > -1 else None
    volatility = returns.std() * math.sqrt(TRADING_DAYS)
    sharpe = (annualized - risk_free.rate) / volatility if annualized is not None and volatility > 0 else None
    max_drawdown = (values / values.cummax() - 1).min()

    beta = None
    benchmark_total = None
    if not benchmark.empty:
        window = benchmark[(benchmark.index >= values.index[0]) & (benchmark.index <= values.index[-1])]
        if len(window) >= 2:
            benchmark_total = window.iloc[-1] / window.iloc[0] - 1
        joined = pd.concat([returns, benchmark.pct_change()], axis=1, join="inner").dropna()
        if len(joined) >= MIN_OBSERVATIONS:
            variance = joined.iloc[:, 1].var()
            if variance > 0:
                beta = joined.iloc[:, 0].cov(joined.iloc[:, 1]) / variance

    return RiskMetrics(
        **common,
        total_return=_num(total_return),
        annualized_return=_num(annualized),
        annualized_volatility=_num(volatility),
        sharpe_ratio=_num(sharpe),
        beta=_num(beta),
        max_drawdown=_num(max_drawdown),
        benchmark_total_return=_num(benchmark_total),
    )


def _performance(values: pd.Series, benchmark: pd.Series) -> list[PerformancePoint]:
    values = values.dropna()
    if len(values) < 2:
        return []
    bench = benchmark.reindex(benchmark.index.union(values.index)).sort_index().ffill().reindex(values.index)
    bench_start = bench.dropna().iloc[0] if not bench.dropna().empty else None

    step = max(1, len(values) // PERFORMANCE_POINTS)
    positions = list(range(0, len(values), step))
    if positions[-1] != len(values) - 1:
        positions.append(len(values) - 1)

    points = []
    for pos in positions:
        bench_value = bench.iloc[pos]
        points.append(
            PerformancePoint(
                date=values.index[pos].date(),
                portfolio=round(float(values.iloc[pos] / values.iloc[0] * 100), 3),
                benchmark=(
                    round(float(bench_value / bench_start * 100), 3)
                    if bench_start and not pd.isna(bench_value)
                    else None
                ),
            )
        )
    return points


def _analyze(request: PortfolioAnalyzeRequest, base_currency: str) -> PortfolioAnalyzeResponse:
    currency_countries = _currency_countries()
    if base_currency not in currency_countries:
        raise UnsupportedCurrencyError(
            f"Unsupported base currency '{base_currency}'. Supported: {sorted(currency_countries)}"
        )
    base_country = currency_countries[base_currency]
    fx = _FxConverter(request.lookback)
    warnings: list[str] = []

    country_inputs = [
        HoldingCountryInput(ticker=h.ticker, exchange=h.exchange, currency=h.currency) for h in request.holdings
    ]
    preliminary = resolve_country(country_inputs, request.country)

    rows = []
    for holding, country_input in zip(request.holdings, country_inputs):
        inference = infer_holding_country(country_input)
        metadata = price_data.fetch_ticker_metadata(holding.ticker)
        history = price_data.fetch_price_history(holding.ticker, request.lookback)

        currency, divisor = _major_currency(history.currency or holding.currency or metadata.get("currency"))
        country_code = inference.country
        if country_code is None:
            country_code = (
                currency_countries[currency].code if currency in currency_countries else preliminary.effective_country
            )
            warnings.append(f"{holding.ticker}: market could not be inferred; treated as {country_code}.")
        country = get_country(country_code)
        currency = currency or country.currency

        local_values = None
        base_values = None
        if history.closes.empty:
            warnings.append(f"{holding.ticker}: no price history found; excluded from valuation and metrics.")
        else:
            local_values = history.closes / divisor * holding.quantity
            base_values = fx.convert(local_values, currency, base_currency)
            if base_values is None:
                warnings.append(f"{holding.ticker}: no {currency}->{base_currency} FX data; excluded from totals.")

        quote_type = (metadata.get("quote_type") or "").upper()
        sector = metadata.get("sector") or ("Funds & ETFs" if quote_type in ("ETF", "MUTUALFUND") else "Unknown")
        rows.append(
            {
                "holding": holding,
                "inference": inference,
                "country": country,
                "currency": currency,
                "name": metadata.get("name"),
                "sector": sector,
                "asset_class": _classify_asset_class(
                    {"quoteType": metadata.get("quote_type"), "category": metadata.get("category")}
                ),
                "local_values": local_values,
                "base_values": base_values,
            }
        )

    valued = [r for r in rows if r["base_values"] is not None]
    frame = (
        pd.concat({r["holding"].ticker: r["base_values"] for r in valued}, axis=1).sort_index().ffill().dropna()
        if valued
        else pd.DataFrame()
    )
    latest_base = frame.iloc[-1] if not frame.empty else pd.Series(dtype=float)
    total_value = float(latest_base.sum()) if not latest_base.empty else 0.0

    analyzed: list[AnalyzedHolding] = []
    for r in rows:
        h = r["holding"]
        value_base = float(latest_base[h.ticker]) if h.ticker in latest_base.index else None
        price = float(r["local_values"].iloc[-1] / h.quantity) if r["local_values"] is not None else None
        r["value_base"] = value_base or 0.0
        analyzed.append(
            AnalyzedHolding(
                ticker=h.ticker,
                name=r["name"],
                country=r["country"].code,
                country_confidence=r["inference"].confidence,
                currency=r["currency"],
                quantity=h.quantity,
                price=_num(price),
                value_local=_num(price * h.quantity) if price is not None else None,
                value_base=_num(value_base),
                weight=_num(value_base / total_value) if value_base and total_value else 0.0,
                sector=r["sector"],
                asset_class=r["asset_class"],
                cost_basis=h.cost_basis,
                unrealized_gain_local=(
                    _num((price - h.cost_basis) * h.quantity) if price is not None and h.cost_basis is not None else None
                ),
            )
        )

    def weights_by(key) -> dict[str, float]:
        totals: dict[str, float] = {}
        for r in rows:
            if total_value and r["value_base"]:
                totals[key(r)] = totals.get(key(r), 0.0) + r["value_base"] / total_value
        return {k: round(v, 6) for k, v in sorted(totals.items(), key=lambda kv: -kv[1])}

    resolution = (
        resolve_country(
            [HoldingCountryInput(**ci.model_dump(exclude={"market_value"}), market_value=r["value_base"])
             for ci, r in zip(country_inputs, rows)],
            request.country,
        )
        if request.holdings and all(r["value_base"] for r in rows)
        else preliminary
    )
    effective = get_country(resolution.effective_country)

    combined = None
    performance: list[PerformancePoint] = []
    if not frame.empty:
        portfolio_series = frame.sum(axis=1)
        base_benchmark = price_data.fetch_price_history(base_country.benchmark_ticker, request.lookback).closes
        combined = _metrics(portfolio_series, base_benchmark, base_country, base_currency)
        performance = _performance(portfolio_series, base_benchmark)
        if combined.total_return is None:
            warnings.append("Not enough price history for risk metrics on the combined portfolio.")

    per_country: list[CountryAnalysis] = []
    for code in sorted({r["country"].code for r in valued}):
        country = get_country(code)
        group = [r for r in valued if r["country"].code == code]
        local_series = [fx.convert(r["local_values"], r["currency"], country.currency) for r in group]
        local_series = [s for s in local_series if s is not None]
        if not local_series:
            continue
        country_frame = pd.concat(local_series, axis=1).sort_index().ffill().dropna()
        country_values = country_frame.sum(axis=1)
        benchmark = price_data.fetch_price_history(country.benchmark_ticker, request.lookback).closes
        value_base = sum(r["value_base"] for r in group)
        per_country.append(
            CountryAnalysis(
                country=code,
                name=country.name,
                currency=country.currency,
                weight=round(value_base / total_value, 6) if total_value else 0.0,
                value_local=round(float(country_values.iloc[-1]), 2) if not country_values.empty else 0.0,
                value_base=round(value_base, 2),
                tickers=[r["holding"].ticker for r in group],
                metrics=_metrics(country_values, benchmark, country, country.currency),
            )
        )

    concentration = None
    holding_weights = [(h.ticker, h.weight) for h in analyzed if h.weight]
    if holding_weights:
        hhi = sum(w * w for _, w in holding_weights)
        top_ticker, top_weight = max(holding_weights, key=lambda tw: tw[1])
        concentration = Concentration(
            hhi=round(hhi, 6),
            effective_holdings=round(1 / hhi, 3),
            largest_position_ticker=top_ticker,
            largest_position_weight=round(top_weight, 6),
        )

    return PortfolioAnalyzeResponse(
        country=resolution,
        country_name=effective.name,
        base_currency=base_currency,
        lookback=request.lookback,
        as_of=frame.index[-1].date() if not frame.empty else date.today(),
        total_value_base=round(total_value, 2),
        holdings=analyzed,
        allocation_by_country=weights_by(lambda r: r["country"].code),
        allocation_by_sector=weights_by(lambda r: r["sector"]),
        allocation_by_asset_class=weights_by(lambda r: r["asset_class"]),
        currency_exposure=weights_by(lambda r: r["currency"]),
        combined_metrics=combined,
        per_country=per_country,
        concentration=concentration,
        performance=performance,
        tax_notes=tax_notes_for(effective),
        tax_advantaged_accounts=accounts_for(effective),
        regulatory_disclaimer=effective.regulatory_disclaimer,
        warnings=warnings,
    )


def _merge_duplicate_tickers(request: PortfolioAnalyzeRequest) -> PortfolioAnalyzeRequest:
    merged: dict[str, PortfolioHoldingIn] = {}
    for holding in request.holdings:
        key = holding.ticker.strip().upper()
        existing = merged.get(key)
        if existing is None:
            merged[key] = holding.model_copy(update={"ticker": key})
            continue
        quantity = existing.quantity + holding.quantity
        cost_basis = None
        if existing.cost_basis is not None and holding.cost_basis is not None:
            cost_basis = (existing.cost_basis * existing.quantity + holding.cost_basis * holding.quantity) / quantity
        merged[key] = existing.model_copy(update={"quantity": quantity, "cost_basis": cost_basis})
    return request.model_copy(update={"holdings": list(merged.values())})


def analyze_portfolio(request: PortfolioAnalyzeRequest) -> PortfolioAnalyzeResponse:
    request = _merge_duplicate_tickers(request)
    if request.base_currency:
        return _analyze(request, request.base_currency.strip().upper())

    preliminary = resolve_country(
        [HoldingCountryInput(ticker=h.ticker, exchange=h.exchange, currency=h.currency) for h in request.holdings],
        request.country,
    )
    result = _analyze(request, get_country(preliminary.effective_country).currency)
    # Value-weighted inference can pick a different dominant country than the count-weighted
    # preliminary guess; if so, re-run in that country's currency (data is cached, so cheap).
    final_currency = get_country(result.country.effective_country).currency
    if final_currency != result.base_currency:
        result = _analyze(request, final_currency)
    return result
