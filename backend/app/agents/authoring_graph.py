from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from app.services.review import advance


class AuthorState(TypedDict, total=False):
    lesson_id: str
    structure_id: str
    structure_name: str
    draft_text: str
    status: str
    decision: str
    reviewer: str
    notes: str
    chunk_id: str

PROMPT = """You are drafting content for an anatomy textbook companion app for students.
Write a clear, student-friendly explanation (3-5 sentences) of: {name} (id: {sid}).
Cover location, main parts and function. Educational only: no diagnosis, treatment or dosing.
Return plain text only."""


def build_authoring_graph(checkpointer, model=None, persist=None):

    def generate(state):
        from app.llm.factory import get_chat_model
        llm = model or get_chat_model(temperature=0.3)
        name = state.get("structure_name") or state["structure_id"]
        reply = llm.invoke(PROMPT.format(name=name, sid=state["structure_id"]))
        return {"draft_text": str(reply.content).strip(), "status": advance("DRAFT", "generate")}

    def to_medical_review(state):
        status = advance(state["status"], "submit")
        status = advance(status, "submit")
        return {"status": status}

    def medical_review(state):
        answer = interrupt({
            "draft_text": state["draft_text"],
            "lesson_id": state["lesson_id"],
            "structure_id": state["structure_id"],
        })
        status = advance(state["status"], answer.get("decision", ""))
        return {
            "decision": answer["decision"],
            "status": status,
            "reviewer": answer.get("reviewer", ""),
            "notes": answer.get("notes", ""),
        }

    def publish_knowledge(state):
        chunk_id = persist(state) if persist else ""
        return {"chunk_id": chunk_id}

    def after_review(state):
        if state["status"] == "APPROVED":
            return "publish_knowledge"
        return END

    g = StateGraph(AuthorState)
    g.add_node("generate", generate)
    g.add_node("to_medical_review", to_medical_review)
    g.add_node("medical_review", medical_review)
    g.add_node("publish_knowledge", publish_knowledge)

    g.add_edge(START, "generate")
    g.add_edge("generate", "to_medical_review")
    g.add_edge("to_medical_review", "medical_review")
    g.add_conditional_edges("medical_review", after_review, ["publish_knowledge", END])
    g.add_edge("publish_knowledge", END)
    return g.compile(checkpointer=checkpointer)
