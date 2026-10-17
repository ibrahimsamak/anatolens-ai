from pathlib import Path
from app.db.session import SessionLocal
from app.graph.anatomy_graph import build_graph

CONTENT = Path(__file__).resolve().parents[3] / "content"
_graph = build_graph(*sorted(CONTENT.glob("*/structures.yaml")))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_anatomy_graph():
    return _graph
