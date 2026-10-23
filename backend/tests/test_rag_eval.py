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

def test_reports_which_tier_answered_and_fallbacks(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    from app.obs.metrics import LLM_FALLBACKS
    rows = [{"question": "How many lumbar vertebrae?", "gold": "5", "structure_id": "s"},
            {"question": "Explain why the lumbar region bears weight", "gold": "w", "structure_id": "s"},
            {"question": "Why is it curved?", "gold": "c", "structure_id": "s"}]
    p = tmp_path / "rag.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    monkeypatch.setattr(rag_eval, "retrieve_chunks", lambda *a: [SimpleNamespace(text="ctx")])
    def explain(sid, q, *a, **k):
        if q.startswith("Why"):   
            LLM_FALLBACKS.labels(primary="openai:gpt-4o").inc()
        return SimpleNamespace(text="answer")
    monkeypatch.setattr(rag_eval, "explain_structure", explain)
    monkeypatch.setattr(rag_eval, "evaluate", lambda ds, metrics: dict.fromkeys(("faithfulness", "answer_relevancy", "context_recall"), 0.9))
    res = run_rag_eval(SimpleNamespace(datasets={"rag": str(p)}), None, _Graph())
    assert (res["routed_cheap"], res["routed_strong"], res["fallbacks"]) == (1, 2, 1)
