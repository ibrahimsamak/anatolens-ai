from functools import lru_cache
from pathlib import Path
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver
from app.db.session import SessionLocal
from app.graph.anatomy_graph import build_graph
from app.core.config import settings
from app.core.security import decode_token, TokenError

CONTENT = Path(__file__).resolve().parents[3] / "content"
_graph = build_graph(*sorted(CONTENT.glob("*/structures.yaml")))
bearer = HTTPBearer(auto_error=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_anatomy_graph():
    return _graph


def optional_user(cred=Depends(bearer)):
    if not cred:
        return None
    try:
        return decode_token(cred.credentials)
    except TokenError:
        raise HTTPException(401, "invalid token", headers={"WWW-Authenticate": "Bearer"})


def current_user(user=Depends(optional_user)):
    if user is None:
        raise HTTPException(401, "missing token", headers={"WWW-Authenticate": "Bearer"})
    return user


def require_role(*roles):
    def check(user=Depends(current_user)):
        if user["role"] not in roles:
            raise HTTPException(403, "insufficient role")
        return user
    return check


@lru_cache
def get_authoring_graph():
    from app.agents.authoring_graph import build_authoring_graph
    from app.services.review import persist_approved

    url = settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    pool = ConnectionPool(url, max_size=5,
                          kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row})
    saver = PostgresSaver(pool)
    saver.setup()
    return build_authoring_graph(saver, persist=persist_approved)
