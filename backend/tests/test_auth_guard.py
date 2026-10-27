import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.security import create_token

LESSON = {"id": "x", "title": "t", "system": "s", "model_url": "u"}

def bearer(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}

@pytest.mark.parametrize("headers", [
    {},
    bearer("not.a.jwt"),
    bearer(create_token("u1", "SUPER_ADMIN", ttl_seconds=-1)),
    bearer(create_token("u1", "SUPER_ADMIN", kind="refresh")),
])
async def test_admin_route_rejects_missing_expired_forged_or_refresh_token(headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/v1/admin/lessons", json=LESSON, headers=headers)
    assert r.status_code == 401

@pytest.mark.parametrize("role", ["STUDENT", "TEACHER", "MEDICAL_REVIEWER"])
async def test_non_editor_cannot_create_content(role):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/v1/admin/lessons", json=LESSON, headers=bearer(create_token("u1", role)))
    assert r.status_code == 403

@pytest.mark.parametrize("role", ["STUDENT", "TEACHER", "CONTENT_EDITOR"])
async def test_only_reviewers_can_resume_a_review(role):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/v1/admin/review/some-thread", json={"decision": "approve"},
                         headers=bearer(create_token("u1", role)))
    assert r.status_code == 403

async def test_me_requires_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/v1/auth/me")
    assert r.status_code == 401
