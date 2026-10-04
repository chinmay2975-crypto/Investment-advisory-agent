from datetime import datetime, timezone

import yfinance as yf

# Matches goal_analysis.DEFAULT_ASSUMED_RETURN: the assumption originally used to project
# whether contributions would meet the goal, so deviation is measured against what the
# recommendation was implicitly built on top of.
DEFAULT_ASSUMED_ANNUAL_RETURN = 0.06


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
    expected_return_pct = DEFAULT_ASSUMED_ANNUAL_RETURN * (elapsed_days / 365.25) * 100

    return {
        "elapsed_days": elapsed_days,
        "realized_return_pct": round(realized_return_pct, 4),
        "expected_return_pct": round(expected_return_pct, 4),
        "deviation_pct": round(realized_return_pct - expected_return_pct, 4),
        "per_instrument": per_instrument,
    }
