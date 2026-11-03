import yfinance as yf

from app.schemas.market_intelligence import GroundingDocument

INDEX_TICKERS = {
    "^GSPC": ("S&P 500", "US"),
    "^DJI": ("Dow Jones Industrial Average", "US"),
    "^IXIC": ("Nasdaq Composite", "US"),
    "^NSEI": ("Nifty 50", "IN"),
    "^BSESN": ("BSE Sensex", "IN"),
    "^FTSE": ("FTSE 100", "GB"),
}
# US SPDR sector ETFs.
SECTOR_TICKERS = {
    "XLK": "Technology",
    "XLF": "Financials",
    "XLE": "Energy",
    "XLV": "Health Care",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLI": "Industrials",
    "XLU": "Utilities",
    "XLB": "Materials",
}


def _pct_change_document(ticker: str, label: str, category: str, country: str) -> GroundingDocument | None:
    history = yf.Ticker(ticker).history(period="5d")
    if history.empty or len(history) < 2:
        return None

    latest_close = history["Close"].iloc[-1]
    prior_close = history["Close"].iloc[-2]
    pct_change = (latest_close - prior_close) / prior_close * 100
    as_of = history.index[-1].to_pydatetime()

    text = (
        f"{label} ({ticker}) closed at {latest_close:.2f} on {as_of.date()}, "
        f"a change of {pct_change:+.2f}% from the prior session."
    )
    return GroundingDocument(
        id=f"{category}:{ticker}:{as_of.date().isoformat()}",
        text=text,
        source="yfinance",
        category=category,
        as_of=as_of,
        metadata={"ticker": ticker, "label": label, "pct_change": round(float(pct_change), 4), "country": country},
    )


def fetch_index_performance() -> list[GroundingDocument]:
    docs = [
        _pct_change_document(t, label, "market_behavior", country) for t, (label, country) in INDEX_TICKERS.items()
    ]
    return [d for d in docs if d is not None]


def fetch_sector_performance() -> list[GroundingDocument]:
    docs = [_pct_change_document(t, label, "sector_performance", "US") for t, label in SECTOR_TICKERS.items()]
    return [d for d in docs if d is not None]
