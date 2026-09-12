from langgraph.graph import StateGraph, START, END

from app.agents.market_intelligence.nodes import (
    market_behavior_node,
    sector_performance_node,
    rates_node,
    inflation_node,
    news_node,
    geopolitical_node,
    ingest_node,
    CATEGORY_KEYS,
)
from app.agents.market_intelligence.state import MarketIntelligenceState

NODE_FUNCS = {
    "market_behavior": market_behavior_node,
    "sector_performance": sector_performance_node,
    "rates": rates_node,
    "inflation": inflation_node,
    "news": news_node,
    "geopolitical": geopolitical_node,
}


def build_market_intelligence_graph():
    graph = StateGraph(MarketIntelligenceState)

    for key in CATEGORY_KEYS:
        graph.add_node(key, NODE_FUNCS[key])
        graph.add_edge(START, key)
        graph.add_edge(key, "ingest")

    graph.add_node("ingest", ingest_node)
    graph.add_edge("ingest", END)

    return graph.compile()


market_intelligence_graph = build_market_intelligence_graph()
