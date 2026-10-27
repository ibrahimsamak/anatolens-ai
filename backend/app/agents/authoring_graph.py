from typing import Callable, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from app.services.review import advance

class AuthorState(TypedDict, total=False):
    lesson_id: str; structure_id: str; structure_name: str
    draft_text: str; status: str; decision: str
    reviewer: str; notes: str; chunk_id: str

PROMPT = ("You are drafting content for an anatomy textbook companion app for students.\n"
          "Write a clear, student-friendly explanation (3-5 sentences) of: {name} (id: {sid}).\n"
          "Cover location, main parts and function. Educational only: no diagnosis, treatment or dosing.\n"
          "Return plain text only.")

def build_authoring_graph(checkpointer, model=None, persist: Callable[[AuthorState], str] | None = None):
    """Draft -> MEDICAL_REVIEW interrupt -> approve (persist as APPROVED knowledge) | reject (back to CONTENT_REVIEW)."""
    def generate(s: AuthorState) -> AuthorState:
        from app.llm.factory import get_chat_model
        llm = model or get_chat_model(temperature=0.3)
        prompt = PROMPT.format(name=s.get("structure_name") or s["structure_id"], sid=s["structure_id"])
        return {"draft_text": str(llm.invoke(prompt).content).strip(), "status": advance("DRAFT", "generate")}

    def to_medical_review(s: AuthorState) -> AuthorState:
        return {"status": advance(advance(s["status"], "submit"), "submit")}

    def medical_review(s: AuthorState) -> AuthorState:
        decision = interrupt({"draft_text": s["draft_text"], "lesson_id": s["lesson_id"],
                              "structure_id": s["structure_id"]})
        new_status = advance(s["status"], decision.get("decision", ""))   
        return {"decision": decision["decision"], "status": new_status,
                "reviewer": decision.get("reviewer", ""), "notes": decision.get("notes", "")}

    def publish_knowledge(s: AuthorState) -> AuthorState:
        return {"chunk_id": persist(s) if persist else ""}

    g = StateGraph(AuthorState)
    g.add_node("generate", generate)
    g.add_node("to_medical_review", to_medical_review)
    g.add_node("medical_review", medical_review)
    g.add_node("publish_knowledge", publish_knowledge)
    g.add_edge(START, "generate")
    g.add_edge("generate", "to_medical_review")
    g.add_edge("to_medical_review", "medical_review")
    g.add_conditional_edges("medical_review", lambda s: "publish_knowledge" if s["status"] == "APPROVED" else END, ["publish_knowledge", END])
    g.add_edge("publish_knowledge", END)
    return g.compile(checkpointer=checkpointer)
