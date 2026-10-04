from langgraph.graph import StateGraph, START, END

from app.agents.scenario.nodes import aggressive_node, balanced_node, conservative_node
from app.agents.scenario.state import ScenarioState


def build_scenario_graph():
    graph = StateGraph(ScenarioState)

    graph.add_node("conservative", conservative_node)
    graph.add_node("balanced", balanced_node)
    graph.add_node("aggressive", aggressive_node)

    for key in ("conservative", "balanced", "aggressive"):
        graph.add_edge(START, key)
        graph.add_edge(key, END)

    return graph.compile()


scenario_graph = build_scenario_graph()
