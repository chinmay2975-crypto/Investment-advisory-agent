"""Monte Carlo goal probability for a suggested allocation.

Replaces the LLM's guessed `goal_probability` with a reproducible simulation: monthly lognormal
portfolio returns from per-asset-class assumptions (app/data/capital_market_assumptions.json),
the goal's current savings, regular contributions and time left. Deterministic (fixed seed) so
the same inputs always give the same number.
"""

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

_ASSUMPTIONS = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "capital_market_assumptions.json").read_text()
)
PATHS = 5000
SEED = 42
PERIODS_PER_YEAR = {"monthly": 12, "quarterly": 4, "annually": 1}

# Allocation keys from the LLM are free text ("Indian equity", "Gilt funds", "Gold ETF"...).
_ASSET_PATTERNS = [
    ("cash", r"cash|money market|liquid|deposit|savings"),
    ("bonds", r"bond|debt|fixed|gilt|treasur|income|credit|ppf|epf"),
    ("gold", r"gold|commodit|precious|silver"),
    ("real_estate", r"real estate|reit|property|invit"),
    ("equity", r"equit|stock|share|index|nifty|s&p|ftse|growth|small|mid|large|elss|etf|fund"),
]


def classify_asset(name: str) -> str:
    lowered = name.lower()
    for asset, pattern in _ASSET_PATTERNS:
        if re.search(pattern, lowered):
            return asset
    return "other"


def _weights(target_allocation: dict) -> dict[str, float]:
    raw = {k: float(v) for k, v in (target_allocation or {}).items() if v is not None and float(v) > 0}
    total = sum(raw.values())
    if total <= 0:
        return {}
    grouped: dict[str, float] = {}
    for name, value in raw.items():
        asset = classify_asset(name)
        grouped[asset] = grouped.get(asset, 0.0) + value / total
    return grouped


def _portfolio_moments(weights: dict[str, float], country: str | None) -> tuple[float, float]:
    table = {**_ASSUMPTIONS["default"], **_ASSUMPTIONS.get(country or "", {})}
    assets = list(weights)
    mean = sum(weights[a] * table[a][0] for a in assets)
    variance = 0.0
    for a in assets:
        for b in assets:
            if a == b:
                corr = 1.0
            else:
                corr = _ASSUMPTIONS["correlations"].get(f"{a}|{b}", _ASSUMPTIONS["correlations"].get(f"{b}|{a}", 0.1))
            variance += weights[a] * weights[b] * table[a][1] * table[b][1] * corr
    return mean, math.sqrt(max(variance, 0.0))


def simulate_goal(target_allocation: dict, goal: dict, country: str | None = None) -> dict | None:
    """Returns {probability, expected_return, volatility, median_final, p10_final, p90_final, months}
    or None when the goal or allocation can't be simulated."""
    weights = _weights(target_allocation)
    target_date = goal.get("target_date")
    if not weights or not goal.get("target_amount") or target_date is None:
        return None
    if isinstance(target_date, str):
        target_date = datetime.fromisoformat(target_date)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    months = round((target_date.replace(tzinfo=None) - now).days / 30.4375)
    if months < 1:
        return None

    mean, vol = _portfolio_moments(weights, country)
    monthly_mu = (math.log1p(mean) - 0.5 * vol**2) / 12
    monthly_sigma = vol / math.sqrt(12)
    per_year = PERIODS_PER_YEAR.get((goal.get("contribution_cadence") or "").lower(), 0)
    monthly_contribution = (goal.get("contribution_amount") or 0.0) * per_year / 12

    rng = np.random.default_rng(SEED)
    values = np.full(PATHS, float(goal.get("current_amount") or 0.0))
    for shock in rng.normal(monthly_mu, monthly_sigma, size=(months, PATHS)):
        values = (values + monthly_contribution) * np.exp(shock)

    p10, p50, p90 = np.percentile(values, [10, 50, 90])
    return {
        "probability": round(float(np.mean(values >= goal["target_amount"])), 4),
        "expected_return": round(mean, 4),
        "volatility": round(vol, 4),
        "median_final": round(float(p50), 2),
        "p10_final": round(float(p10), 2),
        "p90_final": round(float(p90), 2),
        "months": months,
        "paths": PATHS,
    }


def apply_goal_simulation(payload: dict, goal: dict | None, country: str | None = None) -> dict:
    """Overwrite the LLM's goal_probability with the simulated one (keeping the LLM's guess for
    reference). Leaves the payload unchanged when there is no simulatable goal."""
    if not goal:
        return payload
    result = simulate_goal(payload.get("target_allocation") or {}, goal, country)
    if result is None:
        return payload
    return {
        **payload,
        "goal_probability": result["probability"],
        "goal_probability_method": "monte_carlo",
        "llm_goal_probability": payload.get("goal_probability"),
        "simulation": result,
    }
