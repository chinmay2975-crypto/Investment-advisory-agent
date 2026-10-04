import json
from datetime import datetime, timezone
from pathlib import Path

from app.db.models import Holding
from app.services.portfolio_analysis import enrich_holding

_BRACKETS_PATH = Path(__file__).resolve().parent.parent / "data" / "tax_brackets.json"
LONG_TERM_HOLDING_DAYS = 365


def _load_brackets() -> dict[str, list[dict]]:
    with open(_BRACKETS_PATH) as f:
        return json.load(f)


_LONG_TERM_BRACKETS = _load_brackets()


def long_term_capital_gains_rate(taxable_income: float, filing_status: str = "single") -> float:
    try:
        brackets = _LONG_TERM_BRACKETS[filing_status]
    except KeyError:
        raise ValueError(
            f"Unknown filing_status '{filing_status}'. Known statuses: {list(_LONG_TERM_BRACKETS)}"
        )

    for bracket in brackets:
        if bracket["up_to"] is None or taxable_income <= bracket["up_to"]:
            return bracket["rate"]
    return brackets[-1]["rate"]


def classify_holding_period(acquired_at: datetime | None, as_of: datetime | None = None) -> str:
    if acquired_at is None:
        return "unknown"

    reference = as_of or datetime.now(timezone.utc)
    acquired = acquired_at if acquired_at.tzinfo else acquired_at.replace(tzinfo=timezone.utc)
    held_days = (reference - acquired).days
    return "long_term" if held_days > LONG_TERM_HOLDING_DAYS else "short_term"


def analyze_tax(
    holdings: list[Holding],
    ordinary_income_tax_rate: float,
    taxable_income: float,
    filing_status: str = "single",
) -> dict:
    long_term_rate = long_term_capital_gains_rate(taxable_income, filing_status)

    details = []
    total_unrealized_gain = 0.0
    total_estimated_tax = 0.0

    for holding in holdings:
        enriched = enrich_holding(holding)
        cost_basis = enriched["cost_basis"]
        unrealized_gain = (
            (enriched["current_price"] - cost_basis) * enriched["quantity"] if cost_basis is not None else 0.0
        )
        holding_period = classify_holding_period(holding.acquired_at)

        if cost_basis is None or holding_period == "unknown":
            estimated_tax_rate = 0.0
            estimated_tax = 0.0
        elif holding_period == "short_term":
            estimated_tax_rate = ordinary_income_tax_rate
            estimated_tax = max(unrealized_gain, 0.0) * estimated_tax_rate
        else:
            estimated_tax_rate = long_term_rate
            estimated_tax = max(unrealized_gain, 0.0) * estimated_tax_rate

        details.append(
            {
                "ticker": enriched["ticker"],
                "quantity": enriched["quantity"],
                "cost_basis": cost_basis,
                "current_price": enriched["current_price"],
                "unrealized_gain": unrealized_gain,
                "holding_period": holding_period,
                "estimated_tax_rate": estimated_tax_rate,
                "estimated_tax": estimated_tax,
            }
        )
        total_unrealized_gain += unrealized_gain
        total_estimated_tax += estimated_tax

    return {
        "total_unrealized_gain": total_unrealized_gain,
        "total_estimated_tax": total_estimated_tax,
        "holdings": details,
    }
