import pytest
from app.services.adaptive import next_question, record_result
from app.db.session import SessionLocal

@pytest.mark.integration
def test_full_adaptive_round():
    with SessionLocal() as db:
        q = next_question("u-test", "spine_001", db)
        assert q and q.structure_id.startswith("spine.")
        res = record_result("u-test", q.id, q.correct, db)
        assert res["correct"] and 0.0 <= res["mastery"] <= 1.0 and res["reward"] == 1.0
