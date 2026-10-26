import uuid
import structlog
from app.models.learning import DpoPreference

log = structlog.get_logger()

def prompt_for(question: str) -> str:
    return f"Q: {question}\nA: "


def save_pairs(db, question: str, chosen: list[str], rejected: list[str], source: str) -> int:
    rows = [DpoPreference(id=str(uuid.uuid4()), prompt=prompt_for(question), chosen=c, rejected=r, source=source)
            for c in chosen for r in rejected if c.strip() != r.strip()]
    if not rows or db is None:
        return 0
    try:
        db.add_all(rows)
        db.commit()
    except Exception as e:
        db.rollback()
        log.warning("dpo_save_failed", error=type(e).__name__)
        return 0
    return len(rows)