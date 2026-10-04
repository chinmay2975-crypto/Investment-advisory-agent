import yfinance as yf

from app.db.models import Holding

BOND_CATEGORY_KEYWORDS = ("bond", "fixed income", "treasury")


def _classify_asset_class(info: dict) -> str:
    quote_type = (info.get("quoteType") or "").upper()
    category = (info.get("category") or "").lower()
    if any(keyword in category for keyword in BOND_CATEGORY_KEYWORDS):
        return "bonds"
    if quote_type in ("EQUITY", "ETF", "MUTUALFUND"):
        return "stocks"
    return "other"


def enrich_holding(holding: Holding) -> dict:
    info = yf.Ticker(holding.ticker).info or {}
    current_price = (
        info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose") or 0.0
    )
    market_value = current_price * holding.quantity

    return {
        "ticker": holding.ticker,
        "quantity": holding.quantity,
        "cost_basis": holding.cost_basis,
        "current_price": float(current_price),
        "market_value": float(market_value),
        "sector": info.get("sector") or "Unknown",
        "asset_class": _classify_asset_class(info),
        "dividend_yield": float(info.get("dividendYield") or 0.0),
    }


def _risk_profile_for_stock_weight(stock_pct: float) -> str:
    if stock_pct <= 40:
        return "Conservative"
    if stock_pct <= 70:
        return "Balanced"
    return "Aggressive"


def analyze_portfolio(holdings: list[Holding]) -> dict:
    if not holdings:
        return {
            "total_market_value": 0.0,
            "total_cost_basis": 0.0,
            "unrealized_gain_loss": 0.0,
            "asset_allocation": {},
            "sector_exposure": {},
            "weighted_dividend_yield": 0.0,
            "risk_profile": "Unknown",
            "holdings": [],
        }

    enriched = [enrich_holding(h) for h in holdings]
    total_market_value = sum(h["market_value"] for h in enriched)
    total_cost_basis = sum(
        h["cost_basis"] * h["quantity"] for h in enriched if h["cost_basis"] is not None
    )

    asset_allocation: dict[str, float] = {}
    sector_exposure: dict[str, float] = {}
    weighted_dividend_yield = 0.0

    if total_market_value > 0:
        for h in enriched:
            weight = h["market_value"] / total_market_value
            asset_allocation[h["asset_class"]] = asset_allocation.get(h["asset_class"], 0.0) + weight * 100
            sector_exposure[h["sector"]] = sector_exposure.get(h["sector"], 0.0) + weight * 100
            weighted_dividend_yield += weight * h["dividend_yield"]

    return {
        "total_market_value": total_market_value,
        "total_cost_basis": total_cost_basis,
        "unrealized_gain_loss": total_market_value - total_cost_basis,
        "asset_allocation": asset_allocation,
        "sector_exposure": sector_exposure,
        "weighted_dividend_yield": weighted_dividend_yield,
        "risk_profile": _risk_profile_for_stock_weight(asset_allocation.get("stocks", 0.0)),
        "holdings": enriched,
    }
