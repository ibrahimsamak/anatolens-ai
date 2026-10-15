import pytest
from app.agents.supervisor import build_tutor_graph
from app.graph.anatomy_graph import build_graph
from app.db.session import SessionLocal

@pytest.mark.integration
def test_graph_explains_after_tap():
    g = build_tutor_graph(SessionLocal(), build_graph("../content/spine/structures.yaml"))
    out = g.invoke({"active_structure_id": "spine.lumbar_region",
                    "question": "what does it do?", "locale": "en"})
    assert out["answer"] and out["grounded"] is True

@pytest.mark.integration
def test_blocked_question_short_circuits():
    g = build_tutor_graph(SessionLocal(), build_graph("../content/spine/structures.yaml"))
    out = g.invoke({"active_structure_id": "spine.lumbar_region",
                    "question": "prescribe medication for my back", "locale": "en"})
    assert out["grounded"] is False and "educational" in out["answer"].lower()
