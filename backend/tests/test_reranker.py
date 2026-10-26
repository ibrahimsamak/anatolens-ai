import os
import pytest
from app.rl.reranker import Reranker
from app.rag import graphrag
from app.guardrails.pipeline import GuardrailVerdict


def test_missing_model_falls_back_to_identity():
    r = Reranker.load("/nonexistent/path")      # must not raise
    assert not r.active
    assert r.rank("q", ["first", "second"]) == ["first", "second"]

def test_empty_path_falls_back_to_identity():
    assert not Reranker.load("").active

def test_unloadable_model_dir_falls_back(tmp_path):
    (tmp_path / "config.json").write_text("{not json")
    assert Reranker.load(str(tmp_path)).rank("q", ["a", "b"]) == ["a", "b"]


class _Scored(Reranker):
    def __init__(self, scores=None, boom=False):
        self.model, self.tokenizer, self.scores, self.boom = object(), None, scores or {}, boom
    def _score(self, question, answer):
        if self.boom:
            raise RuntimeError("cuda oom")
        return self.scores[answer]

def test_rank_orders_by_score():
    assert _Scored({"a": -3.0, "b": -1.0, "c": -2.0}).rank("q", ["a", "b", "c"]) == ["b", "c", "a"]

def test_scoring_error_falls_back_to_identity():
    assert _Scored(boom=True).rank("q", ["a", "b"]) == ["a", "b"]


@pytest.mark.skipif(not os.getenv("RERANKER_PATH"), reason="set RERANKER_PATH to a trained dpo_out dir")
def test_trained_model_loads_and_ranks():
    r = Reranker.load(os.environ["RERANKER_PATH"])
    assert r.active and sorted(r.rank("what is L1?", ["a lumbar vertebra", "x"])) == ["a lumbar vertebra", "x"]


# --- grounding gate in the tutor ---

class Chunk:
    text, source = "The lumbar region has five vertebrae.", "src1"

class Graph:
    def neighbors(self, sid, hops): return []

class Model:
    def __init__(self): self.temps = []
    def __call__(self, prompt, primary, fallback, temperature=0):
        self.temps.append(temperature)
        return f"answer@{len(self.temps)}"

class Reverse:
    active = True
    def rank(self, q, candidates): return list(reversed(candidates))

@pytest.fixture
def tutor(monkeypatch):
    model = Model()
    monkeypatch.setattr(graphrag, "get_cache", lambda: None)
    monkeypatch.setattr(graphrag, "retrieve_chunks", lambda *a: [Chunk()])
    monkeypatch.setattr(graphrag, "invoke_with_fallback", model)
    return model

def _explain():
    return graphrag.explain_structure("spine.lumbar_region", "what does it do?", "en", None, Graph())

def test_no_reranker_makes_one_call(tutor, monkeypatch):
    monkeypatch.setattr(graphrag, "get_reranker", lambda: Reranker())
    monkeypatch.setattr(graphrag, "check_output", lambda a, ctx: GuardrailVerdict(True))
    assert _explain().text == "answer@1" and tutor.temps == [0.0]

def test_ungrounded_top_pick_is_skipped(tutor, monkeypatch):
    monkeypatch.setattr(graphrag, "get_reranker", lambda: Reverse())
    monkeypatch.setattr(graphrag.settings, "tutor_candidates", 3)
    checked = []
    def grounded(a, ctx):
        checked.append(a)
        return GuardrailVerdict(len(checked) > 1, "ungrounded")   # reranker's favourite is ungrounded
    monkeypatch.setattr(graphrag, "check_output", grounded)
    e = _explain()
    assert len(tutor.temps) == 3 and sorted(tutor.temps)[0] == 0.0
    assert e.grounded and e.text == checked[1] != checked[0]

def test_all_candidates_ungrounded_returns_safe_message(tutor, monkeypatch):
    monkeypatch.setattr(graphrag, "get_reranker", lambda: Reverse())
    monkeypatch.setattr(graphrag, "check_output", lambda a, ctx: GuardrailVerdict(False, "ungrounded"))
    e = _explain()
    assert not e.grounded and "verified" in e.text.lower()
