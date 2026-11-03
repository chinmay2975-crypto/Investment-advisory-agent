from langgraph.graph import END, START, StateGraph

from app.agents.advice.nodes import (
    analyze_portfolio_node,
    generate_advice_node,
    load_country_context_node,
    retrieve_market_context_node,
)
from app.agents.advice.state import AdviceState

# Ordered (node name, human-readable label) -- also drives the SSE stage events.
ADVICE_STAGES = [
    ("analyze_portfolio", "Analysing your portfolio"),
    ("load_country_context", "Loading country conventions"),
    ("retrieve_market_context", "Retrieving market context"),
    ("generate_advice", "Generating suggestion"),
]

_NODE_FUNCS = {
    "analyze_portfolio": analyze_portfolio_node,
    "load_country_context": load_country_context_node,
    "retrieve_market_context": retrieve_market_context_node,
    "generate_advice": generate_advice_node,
}


def build_advice_graph():
    graph = StateGraph(AdviceState)
    names = [name for name, _ in ADVICE_STAGES]
    for name in names:
        graph.add_node(name, _NODE_FUNCS[name])
    graph.add_edge(START, names[0])
    for current, following in zip(names, names[1:]):
        graph.add_edge(current, following)
    graph.add_edge(names[-1], END)
    return graph.compile()


advice_graph = build_advice_graph()
