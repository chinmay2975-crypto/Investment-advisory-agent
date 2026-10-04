from langgraph.graph import StateGraph, START, END

from app.agents.refinement.nodes import classify_constraint_node, refine_recommendation_node
from app.agents.refinement.state import RefinementState


def build_refinement_graph():
    graph = StateGraph(RefinementState)

    graph.add_node("classify_constraint", classify_constraint_node)
    graph.add_node("refine_recommendation", refine_recommendation_node)

    graph.add_edge(START, "classify_constraint")
    graph.add_edge("classify_constraint", "refine_recommendation")
    graph.add_edge("refine_recommendation", END)

    return graph.compile()


refinement_graph = build_refinement_graph()
