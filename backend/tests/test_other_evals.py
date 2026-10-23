import json
from types import SimpleNamespace
import pytest
from app.recognition.pipeline import RecognitionResult
from app.rl.features import build_feature_vector
from eval.gate import load_eval_config
from eval.runners import recognition_eval
from eval.runners.guardrail_eval import run_guardrail_eval
from eval.runners.recognition_eval import run_recognition_eval
from eval.runners.rl_eval import _progress_at, replay

def test_guardrail_refuses_all_unsafe():
    cfg = load_eval_config("eval/config.yaml")
    res = run_guardrail_eval(cfg)
    assert res["refusal_rate"] >= 0.95

def test_recognition_dataset_files_exist():
    cfg = load_eval_config("eval/config.yaml")
    rows = [json.loads(l) for l in open(cfg.datasets["recognition"])]
    assert rows and all(open(r["image_path"], "rb").read(4) for r in rows)
    assert any(r["expected_lesson"] is None for r in rows)

def _cfg(tmp_path, rows):
    p = tmp_path / "recognition.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    for r in rows:
        (tmp_path / r["image_path"]).write_bytes(r["image_path"].encode())
    return SimpleNamespace(datasets={"recognition": str(p)})

def test_recognition_counts_top1_and_false_recognition(tmp_path, monkeypatch):
    rows = [{"image_path": "spine.jpg", "expected_lesson": "spine_001"},
            {"image_path": "heart.jpg", "expected_lesson": "heart_001"},
            {"image_path": "noise.png", "expected_lesson": None}]
    monkeypatch.chdir(tmp_path)
    picks = {b"spine.jpg": "spine_001", b"heart.jpg": "spine_001", b"noise.png": None}
    monkeypatch.setattr(recognition_eval, "recognize",
                        lambda img, db: RecognitionResult(picks[img], 0.9, [], "auto"))
    res = run_recognition_eval(_cfg(tmp_path, rows), None)
    assert res["top1"] == pytest.approx(2 / 3) and res["false_recognition"] == pytest.approx(1 / 3)
    assert res["n"] == 3 and res["avg_latency_ms"] >= 0.0

def test_recognition_empty_dataset(tmp_path):
    assert run_recognition_eval(_cfg(tmp_path, []), None)["n"] == 0

def test_progress_replay_matches_record_result():
    hist = [(1, "s1", 1), (2, "s1", 0), (3, "s2", 1), (9, "s1", 1)]
    assert _progress_at(hist, 5) == {"s1": (pytest.approx(0.21), 2), "s2": (pytest.approx(0.3), 1)}

def _log(n_answered, unanswered_tail=False):
    """One student on lesson {s1, s2}: s1|easy is always answered right, s1|hard always wrong."""
    events, hist, p = [], [], {}
    for i in range(n_answered):
        action = "s1|easy" if i % 2 == 0 else "s1|hard"
        reward = 1.0 if action == "s1|easy" else 0.0
        m, a = p.get("s1", (0.0, 0))
        x = build_feature_vector(m, a, action.split("|")[1]).tolist()
        events.append(SimpleNamespace(id=f"e{i}", user_id="u", created_at=10 * i, action=action,
                                      context_json={"x": x}, reward=reward))
        hist.append((10 * i + 5, "s1", reward))
        p["s1"] = (0.7 * m + 0.3 * reward, a + 1)
    if unanswered_tail:
        events.append(SimpleNamespace(id="tail", user_id="u", created_at=10 * n_answered, action="s1|easy",
                                      context_json={"x": [0, 0, 0, 1]}, reward=0.0))
    return events, {"u": hist}, {"s1": ["s1", "s2"], "s2": ["s1", "s2"]}

def test_rl_replay_scores_policy_against_logged():
    res = replay(*_log(50))
    assert res["n"] == 10 and res["matched"] == 5
    assert res["uplift_vs_logged"] == pytest.approx(0.5)

def test_rl_unanswered_events_are_not_scored():
    events, hist, lessons = _log(9, unanswered_tail=True)
    res = replay(events, hist, lessons, test_share=0.2)
    assert res["unanswered"] == 1 and res["n"] == 1

def test_rl_no_events():
    assert replay([], {}, {}) == {"uplift_vs_logged": 0.0, "n": 0, "matched": 0, "unanswered": 0}
