from datetime import datetime, timezone

import httpx

from app.config import settings
from app.schemas.market_intelligence import GroundingDocument

NEWSAPI_BASE_URL = "https://newsapi.org/v2/everything"


def _fetch_articles(query: str, page_size: int = 5) -> list[dict]:
    response = httpx.get(
        NEWSAPI_BASE_URL,
        params={
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": page_size,
            "apiKey": settings.newsapi_key,
        },
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json().get("articles", [])


def _article_document(article: dict, category: str) -> GroundingDocument | None:
    title = article.get("title")
    if not title:
        return None

    published_at = article.get("publishedAt")
    as_of = (
        datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if published_at
        else datetime.now(timezone.utc)
    )
    description = article.get("description") or ""
    source_name = (article.get("source") or {}).get("name", "unknown")
    url = article.get("url", "")

    text = f"{title}. {description}".strip()
    return GroundingDocument(
        id=f"{category}:{url}",
        text=text,
        source=source_name,
        category=category,
        as_of=as_of,
        metadata={"url": url, "title": title},
    )


def fetch_financial_news() -> list[GroundingDocument]:
    articles = _fetch_articles("stock market OR investing OR federal reserve")
    docs = [_article_document(a, "news") for a in articles]
    return [d for d in docs if d is not None]


def fetch_geopolitical_news() -> list[GroundingDocument]:
    articles = _fetch_articles("geopolitical risk OR sanctions OR trade war OR global conflict economy")
    docs = [_article_document(a, "geopolitical") for a in articles]
    return [d for d in docs if d is not None]
