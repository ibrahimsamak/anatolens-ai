from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from sqlalchemy import select
from app.api.deps import get_anatomy_graph
from app.db.session import SessionLocal
from app.models.content import Lesson, Structure
from app.models.learning import QuizQuestion
from app.rag.retriever import retrieve_chunks

mcp = FastMCP("anatolens-anatomy")
_graph = get_anatomy_graph()


def _lesson_structure_ids(db, lesson_id: str) -> set[str]:
    if db.get(Lesson, lesson_id) is None:
        raise ToolError(f"unknown lesson_id {lesson_id!r}")
    return set(db.execute(select(Structure.id).where(Structure.lesson_id == lesson_id)).scalars())

def _structure(db, structure_id: str) -> Structure:
    s = db.get(Structure, structure_id)
    if s is None:
        raise ToolError(f"unknown structure_id {structure_id!r}")
    return s


@mcp.tool()
def search_knowledge(query: str, lesson_id: str | None = None, locale: str = "en", structure_ids: list[str] | None = None) -> list[dict]:
    """Approved-only knowledge search, scoped to a lesson and/or to known structure ids."""
    if not lesson_id and not structure_ids:
        raise ToolError("pass lesson_id or structure_ids")
    with SessionLocal() as db:
        if structure_ids:
            for sid in structure_ids:
                s = _structure(db, sid)
                if lesson_id and s.lesson_id != lesson_id:
                    raise ToolError(f"{sid!r} is not part of lesson {lesson_id!r}")
            scope = list(structure_ids)
        else:
            scope = sorted(_lesson_structure_ids(db, lesson_id))
        chunks = retrieve_chunks(scope, query, locale, db)     # retriever filters APPROVED + locale
        return [{"text": c.text, "source": c.source, "structure_id": c.structure_id} for c in chunks]


@mcp.tool()
def get_structure(structure_id: str) -> dict:
    """Names, mesh and lesson of one known structure."""
    with SessionLocal() as db:
        s = _structure(db, structure_id)
        return {"id": s.id, "lesson_id": s.lesson_id, "mesh_name": s.mesh_name, "name_en": s.display_name_en, "name_ar": s.display_name_ar}


@mcp.tool()
def graph_neighbors(structure_id: str, hops: int = 1) -> list[str]:
    """Anatomical neighbors of a structure."""
    with SessionLocal() as db:
        _structure(db, structure_id)
    return sorted(_graph.neighbors(structure_id, max(1, min(hops, 3))))


@mcp.tool()
def get_quiz_bank(lesson_id: str, structure_id: str | None = None, limit: int = 20) -> list[dict]:
    """Approved quiz questions for a lesson (optionally one structure)."""
    with SessionLocal() as db:
        known = _lesson_structure_ids(db, lesson_id)
        if structure_id and structure_id not in known:
            raise ToolError(f"{structure_id!r} is not part of lesson {lesson_id!r}")
        stmt = select(QuizQuestion).where(QuizQuestion.lesson_id == lesson_id, QuizQuestion.review_status == "APPROVED")
        if structure_id:
            stmt = stmt.where(QuizQuestion.structure_id == structure_id)
        rows = db.execute(stmt.order_by(QuizQuestion.id).limit(max(1, min(limit, 100)))).scalars()
        return [{"id": q.id, "structure_id": q.structure_id, "difficulty": q.difficulty,
                 "prompt": q.prompt, "choices": q.choices, "correct": q.correct} for q in rows]


if __name__ == "__main__":
    import sys, structlog
    structlog.configure(logger_factory=structlog.PrintLoggerFactory(sys.stderr))   # stdout is the MCP channel
    from app.api.deps import apply_approved_edges
    apply_approved_edges(_graph)
    mcp.run()
