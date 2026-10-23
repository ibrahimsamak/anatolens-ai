from contextlib import nullcontext
import pytest
from app.core.config import settings
from eval import gate
from eval.gate import compare_to_thresholds, load_eval_config

pytestmark = pytest.mark.gate

def test_compare_flags_regression():
    thresholds = {"faithfulness": 0.85}
    ok, failures = compare_to_thresholds({"faithfulness": 0.70}, thresholds)
    assert not ok and "faithfulness" in failures[0]

def test_missing_metric_fails_but_skipped_metric_does_not():
    ok, failures = compare_to_thresholds({}, {"faithfulness": 0.85})
    assert not ok and failures == ["faithfulness: MISSING"]
    assert compare_to_thresholds({}, {"faithfulness": 0.85}, {"faithfulness": "no key"}) == (True, [])

@pytest.fixture
def runners(monkeypatch):
    monkeypatch.setattr(gate, "SessionLocal", lambda: nullcontext("db"))
    monkeypatch.setattr(gate, "build_graph", lambda *p: "graph")
    monkeypatch.setattr(gate, "run_rag_eval", lambda c, db, g: {
        "faithfulness": 0.9, "answer_relevancy": 0.9, "context_recall": 0.9, "n": 2, "unanswerable": 0})
    monkeypatch.setattr(gate, "run_guardrail_eval",
                        lambda c: {"refusal_rate": 1.0, "false_block": 0, "n": 3})
    monkeypatch.setattr(gate, "run_recognition_eval",
                        lambda c, db: {"top1": 0.95, "false_recognition": 0.0, "avg_latency_ms": 4.0, "n": 24})
    def rl(n): monkeypatch.setattr(gate, "run_rl_eval",
                                   lambda c, db: {"uplift_vs_logged": 0.2, "n": n, "matched": n // 2, "unanswered": 0})
    rl(80)
    return rl

def test_run_all_keeps_every_runners_counts(monkeypatch, runners):
    monkeypatch.setattr(settings, "openai_api_key", "k")
    cfg = load_eval_config()
    m, skipped = gate.run_all(cfg)
    assert (m["rag_n"], m["guardrail_n"], m["recognition_n"], m["rl_n"]) == (2, 3, 24, 80)
    assert set(skipped) == {"judge_win_rate"}
    assert compare_to_thresholds(m, cfg.thresholds, skipped) == (True, [])

def test_no_api_key_skips_rag_loudly(monkeypatch, runners):
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(gate, "run_rag_eval", lambda *a: pytest.fail("rag needs the key"))
    m, skipped = gate.run_all(load_eval_config())
    assert "faithfulness" not in m and skipped["faithfulness"] == "OPENAI_API_KEY not set"

def test_too_few_rl_events_skips_uplift(monkeypatch, runners):
    monkeypatch.setattr(settings, "openai_api_key", "k")
    runners(0)
    _, skipped = gate.run_all(load_eval_config())
    assert "rl_uplift_vs_logged" in skipped

def test_main_exits_nonzero_on_regression(monkeypatch, capsys):
    monkeypatch.setattr(gate, "run_all", lambda cfg: ({"faithfulness": 0.1}, {}))
    monkeypatch.setattr(gate, "_log_mlflow", lambda *a: None)
    with pytest.raises(SystemExit) as e:
        gate.main()
    assert e.value.code == 1 and "faithfulness: 0.100 < 0.85" in capsys.readouterr().out

def test_mlflow_logs_run_with_git_sha(tmp_path, monkeypatch):
    import mlflow
    mlflow.set_tracking_uri(f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}")
    try:
        gate._log_mlflow(load_eval_config(), {"faithfulness": 0.9, "note": "x"}, {"judge_win_rate": "skip"})
        run = mlflow.search_runs(output_format="list")[0]
    finally:
        mlflow.set_tracking_uri(None)
    assert run.data.metrics == {"faithfulness": 0.9} and "git_sha" in run.data.params
    assert run.data.tags["skipped.judge_win_rate"] == "skip"
