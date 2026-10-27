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

# who may perform each action
ACTION_ROLES = {
    "generate": EDITORS,
    "submit": EDITORS,
    "publish": EDITORS,
    "approve": REVIEWERS,
    "reject": REVIEWERS,
}


def advance(status: str, action: str) -> str:
    if (status, action) not in TRANSITIONS:
        raise ValueError(f"illegal transition {status} --{action}-->")
    return TRANSITIONS[(status, action)]


def can_perform(role: str, action: str) -> bool:
    return role in ACTION_ROLES.get(action, ())


def persist_approved(state: dict) -> str:
    """Save an approved draft as APPROVED knowledge so the tutor can use it."""
    from app.llm.factory import get_embeddings
    from app.rag.graphrag import get_cache

    chunk = KnowledgeChunk(
        id=str(uuid.uuid4()),
        lesson_id=state["lesson_id"],
        structure_id=state["structure_id"],
        locale="en",
        text=state["draft_text"],
        review_status="APPROVED",
        source="AI-authored, medically reviewed",
        source_version="ai-authoring/v1",
        reviewer=state.get("reviewer"),
        embedding=get_embeddings().embed_query(state["draft_text"]),
    )
    with SessionLocal() as db:
        db.add(chunk)
        db.commit()

    if cache := get_cache():
        cache.clear([state["structure_id"]])
    return chunk.id