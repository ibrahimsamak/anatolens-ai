import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.user import ROLES, User
from app.seed_users import DEMO_USERS, DEMO_PASSWORD, seed_users
from app.db.session import SessionLocal

def test_demo_users_cover_every_role_with_unique_emails():
    assert {r for _, _, r, _ in DEMO_USERS} == set(ROLES)
    assert sum(r == "STUDENT" for _, _, r, _ in DEMO_USERS) >= 2
    assert len({e for _, e, _, _ in DEMO_USERS}) == len(DEMO_USERS)

@pytest.mark.integration
async def test_seed_is_idempotent_and_each_demo_user_can_log_in():
    with SessionLocal() as db:
        seed_users(db)
        seed_users(db)
        assert db.query(User).filter(User.email.in_([e for _, e, _, _ in DEMO_USERS])).count() == len(DEMO_USERS)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        for _, email, role, _ in DEMO_USERS:
            r = await c.post("/api/v1/auth/login", json={"email": email, "password": DEMO_PASSWORD})
            assert r.status_code == 200 and r.json()["user"]["role"] == role
