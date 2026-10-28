from functools import lru_cache
from pathlib import Path
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver
from app.db.session import SessionLocal
from app.graph.anatomy_graph import build_graph_backend
from app.core.config import settings
from app.core.logging import log
from app.core.security import decode_token, TokenError

CONTENT = Path(__file__).resolve().parents[3] / "content"
_graph = build_graph_backend(*sorted(CONTENT.glob("*/structures.yaml")))
bearer = HTTPBearer(auto_error=False)


def apply_approved_edges(graph=None):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.core.config import sqlalchemy_database_url
    from app.models.graph_ops import EdgeProposal

    graph = graph or _graph
    engine = create_engine(sqlalchemy_database_url(), connect_args={"connect_timeout": 5})
    try:
        with Session(engine) as db:
            edges = db.query(EdgeProposal).filter_by(status="APPROVED").all()
    except Exception as e:
        log.warning("approved_edges_not_loaded", error=str(e))
        return 0
    finally:
        engine.dispose()
    for e in edges:
        graph.add_edge(e.subject_id, e.predicate, e.object_id)
    return len(edges)


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
