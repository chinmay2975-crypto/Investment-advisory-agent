from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd

from app.services import macro_data, market_data, news_data


def test_fetch_index_performance_normalizes_documents():
    fake_history = pd.DataFrame(
        {"Close": [4000.0, 4100.0]},
        index=pd.to_datetime(["2026-01-01", "2026-01-02"], utc=True),
    )
    with patch("app.services.market_data.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = fake_history
        docs = market_data.fetch_index_performance()

    assert len(docs) == len(market_data.INDEX_TICKERS)
    for doc in docs:
        assert doc.category == "market_behavior"
        assert doc.source == "yfinance"
        assert "pct_change" in doc.metadata


def test_fetch_index_performance_skips_empty_history():
    with patch("app.services.market_data.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = pd.DataFrame()
        docs = market_data.fetch_index_performance()

    assert docs == []


def test_fetch_rates_normalizes_documents():
    fake_response = MagicMock()
    fake_response.json.return_value = {
        "observations": [{"date": "2026-01-01", "value": "5.33"}]
    }
    fake_response.raise_for_status = MagicMock()

    with patch("app.services.macro_data.httpx.get", return_value=fake_response):
        docs = macro_data.fetch_rates()

    assert len(docs) == len(macro_data.RATE_SERIES)
    for doc in docs:
        assert doc.category == "rates"
        assert doc.source == "FRED"
        assert doc.metadata["value"] == 5.33


def test_fetch_rates_skips_missing_values():
    fake_response = MagicMock()
    fake_response.json.return_value = {"observations": [{"date": "2026-01-01", "value": "."}]}
    fake_response.raise_for_status = MagicMock()

    with patch("app.services.macro_data.httpx.get", return_value=fake_response):
        docs = macro_data.fetch_rates()

    assert docs == []


def test_fetch_financial_news_normalizes_documents():
    fake_response = MagicMock()
    fake_response.json.return_value = {
        "articles": [
            {
                "title": "Markets rally on rate cut hopes",
                "description": "Stocks rose broadly.",
                "publishedAt": "2026-01-01T12:00:00Z",
                "source": {"name": "Reuters"},
                "url": "https://example.com/a1",
            }
        ]
    }
    fake_response.raise_for_status = MagicMock()

    with patch("app.services.news_data.httpx.get", return_value=fake_response):
        docs = news_data.fetch_financial_news()

    assert len(docs) == 1
    assert docs[0].category == "news"
    assert docs[0].source == "Reuters"
    assert docs[0].as_of == datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_fetch_financial_news_skips_articles_without_title():
    fake_response = MagicMock()
    fake_response.json.return_value = {"articles": [{"title": None}]}
    fake_response.raise_for_status = MagicMock()

    with patch("app.services.news_data.httpx.get", return_value=fake_response):
        docs = news_data.fetch_financial_news()

    assert docs == []
