import pytest
from app.graph.anatomy_graph import build_graph
from app.rag.graphrag import explain_structure
from app.db.session import SessionLocal

@pytest.mark.integration
def test_explain_lumbar_is_grounded_and_cited():
    g = build_graph("../content/spine/structures.yaml")
    e = explain_structure("spine.lumbar_region", "what does it do?", "en", SessionLocal(), g)
    assert e.grounded and e.citations and "lumbar" in e.text.lower()

@pytest.mark.integration
def test_structure_without_approved_knowledge_returns_safe_message():
    g = build_graph("../content/spine/structures.yaml")
    e = explain_structure("spine.coccygeal_region", "x", "en", SessionLocal(), g)
    assert not e.grounded and "verified" in e.text.lower()
