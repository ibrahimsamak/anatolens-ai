import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import create_token

@pytest.fixture
def email():
    e = f"s-{uuid.uuid4().hex[:8]}@x.com"
    yield e
    with SessionLocal() as db:
        db.query(User).filter_by(email=e).delete()
        db.commit()

def bearer(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}

@pytest.mark.integration
async def test_register_login_and_role_guard(email):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        reg = await c.post("/api/v1/auth/register", json={"email": email, "password": "p4ssword", "role": "STUDENT"})
        tok = (await c.post("/api/v1/auth/login", json={"email": email, "password": "p4ssword"})).json()["access_token"]
        me = await c.get("/api/v1/auth/me", headers=bearer(tok))
        r = await c.post("/api/v1/admin/lessons", json={"id": "x", "title": "t", "system": "s", "model_url": "u"},
                         headers=bearer(tok))
    assert reg.status_code == 201 and reg.json()["role"] == "STUDENT"
    assert me.json()["email"] == email
    assert r.status_code == 403   # STUDENT cannot create content

@pytest.mark.integration
async def test_wrong_password_and_duplicate_email(email):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await c.post("/api/v1/auth/register", json={"email": email, "password": "p4ssword"})
        dup = await c.post("/api/v1/auth/register", json={"email": email.upper(), "password": "other123"})
        bad = await c.post("/api/v1/auth/login", json={"email": email, "password": "nope"})
    assert dup.status_code == 409
    assert bad.status_code == 401

@pytest.mark.integration
async def test_anonymous_cannot_self_register_privileged_role(email):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/v1/auth/register", json={"email": email, "password": "p4ssword", "role": "SUPER_ADMIN"})
        ok = await c.post("/api/v1/auth/register", json={"email": email, "password": "p4ssword", "role": "MEDICAL_REVIEWER"},
                          headers=bearer(create_token("admin", "SUPER_ADMIN")))
    assert r.status_code == 403
    assert ok.status_code == 201 and ok.json()["role"] == "MEDICAL_REVIEWER"

@pytest.mark.integration
async def test_refresh_issues_new_access_token_and_rejects_access_token(email):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await c.post("/api/v1/auth/register", json={"email": email, "password": "p4ssword"})
        tokens = (await c.post("/api/v1/auth/login", json={"email": email, "password": "p4ssword"})).json()
        r = await c.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        wrong = await c.post("/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]})
        me = await c.get("/api/v1/auth/me", headers=bearer(r.json()["access_token"]))
    assert r.status_code == 200 and me.json()["email"] == email
    assert wrong.status_code == 401
