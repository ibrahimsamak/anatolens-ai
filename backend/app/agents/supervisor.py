from langgraph.graph import StateGraph, START, END
from app.agents.state import TutorState
from app.agents import nodes as default_nodes

def build_tutor_graph(db, graph, node_factory=default_nodes):
    g = StateGraph(TutorState)
    g.add_node("guard", node_factory.make_guard_node())
    g.add_node("recognize", node_factory.make_recognition_node(db))
    g.add_node("explain", node_factory.make_explain_node(db, graph))
    g.add_edge(START, "guard")
    g.add_edge("guard", "recognize")
    g.add_edge("recognize", "explain")
    g.add_edge("explain", END)
    return g.compile()

