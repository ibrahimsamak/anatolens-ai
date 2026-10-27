from pathlib import Path
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.db.session import SessionLocal
from app.graph.anatomy_graph import build_graph
from app.core.security import decode_token, TokenError

CONTENT = Path(__file__).resolve().parents[3] / "content"
_graph = build_graph(*sorted(CONTENT.glob("*/structures.yaml")))
_bearer = HTTPBearer(auto_error=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_anatomy_graph():
    return _graph

def optional_user(cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict | None:
    if not cred:
        return None
    try:
        return decode_token(cred.credentials)
    except TokenError:
        raise HTTPException(401, "invalid token", headers={"WWW-Authenticate": "Bearer"})

def current_user(user: dict | None = Depends(optional_user)) -> dict:
    if user is None:
        raise HTTPException(401, "missing token", headers={"WWW-Authenticate": "Bearer"})
    return user

def require_role(*roles: str):
    def dep(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(403, "insufficient role")
        return user
    return dep

_authoring_graph = None

def get_authoring_graph():
    global _authoring_graph
    if _authoring_graph is None:
        from psycopg_pool import ConnectionPool
        from psycopg.rows import dict_row
        from langgraph.checkpoint.postgres import PostgresSaver
        from app.core.config import settings
        from app.agents.authoring_graph import build_authoring_graph
        from app.services.review import persist_approved
        url = settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        pool = ConnectionPool(url, max_size=5, kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row})
        saver = PostgresSaver(pool)
        saver.setup()
        _authoring_graph = build_authoring_graph(saver, persist=persist_approved)
    return _authoring_graph
