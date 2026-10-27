import pytest
from httpx import AsyncClient, ASGITransport
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from app.main import app
from app.api import deps
from app.agents.authoring_graph import build_authoring_graph
from app.core.config import settings
from app.core.security import create_token
from app.db.session import SessionLocal
from app.models.review import ReviewTask

DRAFT = "The lumbar region has five large vertebrae."

def bearer(role: str) -> dict:
    return {"Authorization": f"Bearer {create_token(f'test-{role.lower()}', role)}"}

def postgres_graph(persisted: list):
    """A fresh saver + graph each call, like a new server process pointing at the same DB."""
    import psycopg
    from psycopg.rows import dict_row
    from langgraph.checkpoint.postgres import PostgresSaver
    conn = psycopg.connect(settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1),
                           autocommit=True, prepare_threshold=0, row_factory=dict_row)
    saver = PostgresSaver(conn)
    saver.setup()
    return build_authoring_graph(saver, model=FakeListChatModel(responses=[DRAFT]),
                                 persist=lambda s: persisted.append(s) or "chunk-1")

@pytest.fixture
def authoring(monkeypatch):
    persisted, threads = [], []
    app.dependency_overrides[deps.get_authoring_graph] = lambda: postgres_graph(persisted)
    yield persisted, threads
    app.dependency_overrides.pop(deps.get_authoring_graph, None)
    with SessionLocal() as db:
        db.query(ReviewTask).filter(ReviewTask.thread_id.in_(threads)).delete()
        db.commit()

@pytest.mark.integration
async def test_author_pause_survive_restart_then_approve(authoring):
    persisted, threads = authoring
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        started = await c.post("/api/v1/admin/lessons/spine_001/author?structure_id=spine.lumbar_region",
                               headers=bearer("CONTENT_EDITOR"))
        tid = started.json()["thread_id"]
        threads.append(tid)
        queue = (await c.get("/api/v1/admin/reviews", headers=bearer("MEDICAL_REVIEWER"))).json()
        # the dependency override builds a brand-new saver per request -> resume works across "restarts"
        done = await c.post(f"/api/v1/admin/review/{tid}", json={"decision": "approve"}, headers=bearer("MEDICAL_REVIEWER"))
        again = await c.post(f"/api/v1/admin/review/{tid}", json={"decision": "reject"}, headers=bearer("MEDICAL_REVIEWER"))
    assert started.status_code == 201 and started.json()["status"] == "MEDICAL_REVIEW" and started.json()["interrupted"]
    assert any(t["thread_id"] == tid and t["draft_text"] == DRAFT for t in queue)
    assert done.json()["status"] == "APPROVED" and len(persisted) == 1
    assert again.status_code == 409   # already decided

@pytest.mark.integration
async def test_reject_returns_to_content_review_and_is_not_persisted(authoring):
    persisted, threads = authoring
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        tid = (await c.post("/api/v1/admin/lessons/spine_001/author?structure_id=spine.lumbar_region",
                            headers=bearer("SUPER_ADMIN"))).json()["thread_id"]
        threads.append(tid)
        r = await c.post(f"/api/v1/admin/review/{tid}", json={"decision": "reject", "notes": "cite a source"},
                         headers=bearer("MEDICAL_REVIEWER"))
    assert r.json()["status"] == "CONTENT_REVIEW" and r.json()["notes"] == "cite a source"
    assert not persisted

@pytest.mark.integration
async def test_author_unknown_structure_404_and_unknown_review_404(authoring):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        a = await c.post("/api/v1/admin/lessons/spine_001/author?structure_id=heart.left_ventricle",
                         headers=bearer("CONTENT_EDITOR"))
        r = await c.post("/api/v1/admin/review/nope", json={"decision": "approve"}, headers=bearer("MEDICAL_REVIEWER"))
    assert a.status_code == 404 and r.status_code == 404
