import pytest
from eval.runners import rag_eval
from eval.runners.rag_eval import run_rag_eval
from eval.gate import load_eval_config

@pytest.mark.integration
def test_rag_eval_reports_metrics():
    from app.db.session import SessionLocal
    from app.graph.anatomy_graph import build_graph
    cfg = load_eval_config("eval/config.yaml")
    res = run_rag_eval(cfg, SessionLocal(), build_graph("../content/spine/structures.yaml"))
    assert 0.0 <= res["faithfulness"] <= 1.0 and res["n"] >= 2

class _Graph:
    def neighbors(self, sid, hops): return []

def test_gold_not_in_kb_is_unanswerable_not_zero(monkeypatch):
    monkeypatch.setattr(rag_eval, "retrieve_chunks", lambda *a: [])
    monkeypatch.setattr(rag_eval, "evaluate", lambda *a, **k: pytest.fail("nothing to score"))
    res = run_rag_eval(load_eval_config("eval/config.yaml"), None, _Graph())
    assert res["n"] == 0 and res["unanswerable"] == 2
