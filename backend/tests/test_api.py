import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.integration
async def test_explain_endpoint_returns_grounded_answer():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/v1/structures/spine.lumbar_region/explain",
                         json={"question": "what does it do?", "locale": "en"})
    assert r.status_code == 200
    body = r.json()
    assert body["grounded"] and body["citations"]

@pytest.mark.integration
async def test_recognition_rejects_unknown_image():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/v1/recognition/page", files={"file": ("x.png", b"\x89PNG\r\n", "image/png")})
    assert r.json()["decision"] in {"rescan", "confirm", "auto"}


import asyncio, json, time
from app.api import tutor
from app.api.deps import get_db, get_anatomy_graph
from app.rag.graphrag import Explanation

@pytest.fixture
def slow_tutor(monkeypatch):
    def fake_explain(structure_id, question, locale, db, graph):
        time.sleep(1.0)
        return Explanation(f"{structure_id} explained", ["src"], True)
    monkeypatch.setattr(tutor, "explain_structure", fake_explain)
    app.dependency_overrides[get_db] = lambda: iter([None])
    yield
    app.dependency_overrides.pop(get_db, None)

async def test_tutor_ask_does_not_block_other_requests(slow_tutor):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        async def ask():
            return await c.post("/api/v1/tutor/ask?structure_id=spine.lumbar_region", json={"question": "what?"})
        async def health():
            t = time.perf_counter()
            await asyncio.sleep(0.1)
            await c.get("/healthz")
            return time.perf_counter() - t
        r, health_s = await asyncio.gather(ask(), health())
    assert health_s < 0.5, f"/healthz waited {health_s:.2f}s behind the LLM call"
    events = [json.loads(l[5:]) for l in r.text.splitlines() if l.startswith("data:")]
    assert events[-1] == {"done": True, "citations": ["src"], "grounded": True}

async def test_tutor_ask_applies_input_guardrail(slow_tutor):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/v1/tutor/ask?structure_id=spine.lumbar_region",
                         json={"question": "diagnose my back pain"})
    events = [json.loads(l[5:]) for l in r.text.splitlines() if l.startswith("data:")]
    assert "educational" in events[0]["token"] and events[-1]["grounded"] is False

def test_api_graph_covers_every_lesson_pack():
    g = get_anatomy_graph()
    assert "spine.sacral_region" in g.neighbors("spine.lumbar_region")
    assert "heart.mitral_valve" in g.neighbors("heart.left_ventricle")
