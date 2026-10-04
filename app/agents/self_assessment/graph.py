from langgraph.graph import StateGraph, START, END

from app.agents.self_assessment.nodes import evaluate_node, reflect_node, retrieve_similar_node
from app.agents.self_assessment.state import SelfAssessmentState


def build_self_assessment_graph():
    graph = StateGraph(SelfAssessmentState)

    graph.add_node("evaluate", evaluate_node)
    graph.add_node("retrieve_similar", retrieve_similar_node)
    graph.add_node("reflect", reflect_node)

    graph.add_edge(START, "evaluate")
    graph.add_edge("evaluate", "retrieve_similar")
    graph.add_edge("retrieve_similar", "reflect")
    graph.add_edge("reflect", END)

    return graph.compile()


self_assessment_graph = build_self_assessment_graph()
