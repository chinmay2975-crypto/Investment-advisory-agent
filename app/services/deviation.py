from datetime import datetime, timezone

import yfinance as yf

from app.countries import get_country, infer_portfolio_country
from app.schemas.country import HoldingCountryInput

# Used only when a suggestion carries no simulated expected return (older suggestions, or ones
# without a goal); matches goal_analysis.DEFAULT_ASSUMED_RETURN.
DEFAULT_ASSUMED_ANNUAL_RETURN = 0.06
DEFAULT_BENCHMARK_COUNTRY = "US"


def _price_at_or_after(ticker: str, as_of: datetime) -> float | None:
    history = yf.Ticker(ticker).history(start=as_of.date().isoformat())
    if history.empty:
        return None
    return float(history["Close"].iloc[0])


def _latest_price(ticker: str) -> float | None:
    history = yf.Ticker(ticker).history(period="5d")
    if history.empty:
        return None
    return float(history["Close"].iloc[-1])


def compute_deviation(payload: dict, generated_at: datetime, as_of: datetime | None = None) -> dict:
    as_of = as_of or datetime.now(timezone.utc)
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)

    elapsed_days = max((as_of - generated_at).days, 1)
    instruments = payload.get("suggested_instruments") or []

    per_instrument = {}
    returns = []
    for ticker in instruments:
        start_price = _price_at_or_after(ticker, generated_at)
        end_price = _latest_price(ticker)
        if not start_price or not end_price:
            continue
        pct_change = (end_price - start_price) / start_price
        per_instrument[ticker] = round(pct_change * 100, 4)
        returns.append(pct_change)

    realized_return_pct = (sum(returns) / len(returns) * 100) if returns else 0.0

    # Expected: the return the goal simulation assumed for this exact allocation, if available.
    simulated = (payload.get("simulation") or {}).get("expected_return")
    annual_expected = simulated if simulated is not None else DEFAULT_ASSUMED_ANNUAL_RETURN
    expected_return_pct = annual_expected * (elapsed_days / 365.25) * 100

    # Benchmark: the index of the market the suggested instruments trade in, over the same window.
    benchmark = get_country(_benchmark_country(instruments))
    benchmark_return_pct = None
    if returns:  # nothing to compare when no suggested instrument has prices
        try:
            start = _price_at_or_after(benchmark.benchmark_ticker, generated_at)
            end = _latest_price(benchmark.benchmark_ticker)
            if start and end:
                benchmark_return_pct = (end - start) / start * 100
        except Exception:  # noqa: BLE001 - benchmark is context, not required for the evaluation
            benchmark_return_pct = None

    return {
        "elapsed_days": elapsed_days,
        "realized_return_pct": round(realized_return_pct, 4),
        "expected_return_pct": round(expected_return_pct, 4),
        "expected_return_source": "simulated_allocation" if simulated is not None else "default_assumption",
        "deviation_pct": round(realized_return_pct - expected_return_pct, 4),
        "benchmark_ticker": benchmark.benchmark_ticker,
        "benchmark_name": benchmark.benchmark_name,
        "benchmark_return_pct": round(benchmark_return_pct, 4) if benchmark_return_pct is not None else None,
        "excess_vs_benchmark_pct": (
            round(realized_return_pct - benchmark_return_pct, 4) if benchmark_return_pct is not None else None
        ),
        "per_instrument": per_instrument,
    }


def _benchmark_country(instruments: list[str]) -> str:
    inference = infer_portfolio_country([HoldingCountryInput(ticker=t) for t in instruments if t])
    return inference.inferred_country or DEFAULT_BENCHMARK_COUNTRY
