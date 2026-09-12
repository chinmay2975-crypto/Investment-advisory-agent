from app.agents.market_intelligence.state import MarketIntelligenceState
from app.services import chroma_client, macro_data, market_data, news_data


def market_behavior_node(state: MarketIntelligenceState) -> dict:
    return {"market_behavior": market_data.fetch_index_performance()}


def sector_performance_node(state: MarketIntelligenceState) -> dict:
    return {"sector_performance": market_data.fetch_sector_performance()}


def rates_node(state: MarketIntelligenceState) -> dict:
    return {"rates": macro_data.fetch_rates()}


def inflation_node(state: MarketIntelligenceState) -> dict:
    return {"inflation": macro_data.fetch_inflation()}


def news_node(state: MarketIntelligenceState) -> dict:
    return {"news": news_data.fetch_financial_news()}


def geopolitical_node(state: MarketIntelligenceState) -> dict:
    return {"geopolitical": news_data.fetch_geopolitical_news()}


CATEGORY_KEYS = [
    "market_behavior",
    "sector_performance",
    "rates",
    "inflation",
    "news",
    "geopolitical",
]


def ingest_node(state: MarketIntelligenceState) -> dict:
    all_docs = [doc for key in CATEGORY_KEYS for doc in state.get(key, [])]
    count = chroma_client.ingest_documents(all_docs)
    return {"documents_ingested": count}
