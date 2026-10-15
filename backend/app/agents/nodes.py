from typing import Callable
from app.agents.state import TutorState
from app.recognition.pipeline import recognize
from app.rag.graphrag import explain_structure
from app.guardrails.pipeline import check_input

NodeFn = Callable[[TutorState], TutorState]

def make_guard_node() -> NodeFn:
    def guard_node(s: TutorState) -> TutorState:
        v = check_input(s.get("question", ""))
        if not v.allowed:
            return {"answer": v.redirect, "grounded": False, "citations": []}
        return {}
    return guard_node

def make_recognition_node(db) -> NodeFn:
    def recognize_node(s: TutorState) -> TutorState:
        if not s.get("image_bytes"):
            return {}
        r = recognize(s["image_bytes"], db)
        return {"lesson_id": r.lesson_id, "confidence": r.confidence, "decision": r.decision}
    return recognize_node

def make_explain_node(db, graph) -> NodeFn:
    def explain_node(s: TutorState) -> TutorState:
        if s.get("answer"):
            return {}
        e = explain_structure(s["active_structure_id"], s.get("question", ""),
                              s.get("locale", "en"), db, graph)
        return {"answer": e.text, "citations": e.citations, "grounded": e.grounded}
    return explain_node