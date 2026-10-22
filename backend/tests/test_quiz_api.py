import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.integration
async def test_next_then_submit():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        nq = (await c.post("/api/v1/quiz/next", json={"user_id": "u1", "lesson_id": "spine_001"})).json()
        res = await c.post("/api/v1/quiz/submit",
                           json={"user_id": "u1", "question_id": nq["id"], "answer": nq["correct"]})
        prog = (await c.get("/api/v1/progress/u1")).json()
    assert res.json()["correct"] is True
    assert any(p["structure_id"] == nq["structure_id"] and p["attempts"] >= 1 for p in prog)

@pytest.mark.integration
async def test_submit_unknown_question_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/v1/quiz/submit", json={"user_id": "u-404-probe", "question_id": "nope", "answer": "x"})
        prog = (await c.get("/api/v1/progress/u-404-probe")).json()
    assert r.status_code == 404 and prog == []
