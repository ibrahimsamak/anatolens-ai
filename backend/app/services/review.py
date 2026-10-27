import uuid
from app.db.session import SessionLocal
from app.models.content import KnowledgeChunk

STATUSES = ["DRAFT", "AI_GENERATED", "CONTENT_REVIEW", "MEDICAL_REVIEW", "APPROVED", "PUBLISHED"]
TRANSITIONS = {
    ("DRAFT", "generate"): "AI_GENERATED",
    ("AI_GENERATED", "submit"): "CONTENT_REVIEW",
    ("CONTENT_REVIEW", "submit"): "MEDICAL_REVIEW",
    ("MEDICAL_REVIEW", "approve"): "APPROVED",
    ("MEDICAL_REVIEW", "reject"): "CONTENT_REVIEW",
    ("APPROVED", "publish"): "PUBLISHED",
}
EDITORS = ("CONTENT_EDITOR", "SUPER_ADMIN")
REVIEWERS = ("MEDICAL_REVIEWER", "SUPER_ADMIN")
ACTION_ROLES = {"generate": EDITORS, "submit": EDITORS, "publish": EDITORS, "approve": REVIEWERS, "reject": REVIEWERS}

def advance(status: str, action: str) -> str:
    key = (status, action)
    if key not in TRANSITIONS:
        raise ValueError(f"illegal transition {status} --{action}-->")
    return TRANSITIONS[key]

def can_perform(role: str, action: str) -> bool:
    return role in ACTION_ROLES.get(action, ())

def persist_approved(state: dict) -> str:
    """Write an approved draft into the knowledge base so the tutor can retrieve it."""
    from app.llm.factory import get_embeddings
    from app.rag.graphrag import get_cache
    chunk_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(KnowledgeChunk(
            id=chunk_id, lesson_id=state["lesson_id"], structure_id=state["structure_id"], locale="en",
            text=state["draft_text"], review_status="APPROVED", source="AI-authored, medically reviewed",
            source_version="ai-authoring/v1", reviewer=state.get("reviewer"),
            embedding=get_embeddings().embed_query(state["draft_text"])))
        db.commit()
    if cache := get_cache():
        cache.clear([state["structure_id"]])
    return chunk_id
