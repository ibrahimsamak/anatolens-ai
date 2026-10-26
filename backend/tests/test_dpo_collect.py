import pytest
from app.rl.dpo_collect import save_pairs, prompt_for
from app.rl.reranker import Reranker
from app.rag import graphrag
from app.guardrails.pipeline import GuardrailVerdict
from eval.runners import judge_eval


class FakeDb:
    def __init__(self, fail=False): self.rows, self.fail, self.rolled_back = [], fail, False
    def add_all(self, rows):
        if self.fail: raise RuntimeError("db down")
        self.rows += rows
    def commit(self): pass
    def rollback(self): self.rolled_back = True


def test_saves_one_row_per_chosen_rejected_pair():
    db = FakeDb()
    assert save_pairs(db, "what is L1?", ["good"], ["bad1", "bad2"], "tutor") == 2
    assert {(r.prompt, r.chosen, r.rejected, r.source) for r in db.rows} == {
        ("Q: what is L1?\nA: ", "good", "bad1", "tutor"), ("Q: what is L1?\nA: ", "good", "bad2", "tutor")}

def test_prompt_matches_reranker_scoring_prefix():
    assert prompt_for("q") == "Q: q\nA: "

def test_identical_pair_is_skipped():
    db = FakeDb()
    assert save_pairs(db, "q", ["same"], [" same "], "tutor") == 0 and db.rows == []

def test_no_db_is_a_no_op():
    assert save_pairs(None, "q", ["good"], ["bad"], "tutor") == 0

def test_db_error_never_raises():
    db = FakeDb(fail=True)
    assert save_pairs(db, "q", ["good"], ["bad"], "tutor") == 0 and db.rolled_back


# --- live collection in the tutor ---

class Chunk:
    text, source = "The lumbar region has five vertebrae.", "src1"

class Graph:
    def neighbors(self, sid, hops): return []

@pytest.fixture
def tutor(monkeypatch):
    answers = iter(["good answer", "bad answer 1", "bad answer 2"])
    saved = []
    monkeypatch.setattr(graphrag, "get_cache", lambda: None)
    monkeypatch.setattr(graphrag, "retrieve_chunks", lambda *a: [Chunk()])
    monkeypatch.setattr(graphrag, "get_reranker", lambda: Reranker())   # no trained model yet
    monkeypatch.setattr(graphrag, "_candidates", lambda prompt, primary, n: [next(answers) for _ in range(n)])
    monkeypatch.setattr(graphrag, "save_pairs", lambda db, q, chosen, rejected, source: saved.append((q, chosen, rejected, source)))
    monkeypatch.setattr(graphrag, "check_output", lambda a, ctx: GuardrailVerdict(a.startswith("good"), "ungrounded"))
    monkeypatch.setattr(graphrag.settings, "tutor_candidates", 3)
    return saved

def _explain():
    return graphrag.explain_structure("spine.lumbar_region", "what does it do?", "en", None, Graph())

def test_collect_on_saves_grounded_vs_ungrounded(tutor, monkeypatch):
    monkeypatch.setattr(graphrag.settings, "dpo_collect", True)
    e = _explain()
    assert e.grounded and e.text == "good answer" and e.citations == ["src1"]
    assert tutor == [("what does it do?", ["good answer"], ["bad answer 1", "bad answer 2"], "tutor")]

def test_collect_on_all_ungrounded_returns_safe_message(tutor, monkeypatch):
    monkeypatch.setattr(graphrag.settings, "dpo_collect", True)
    monkeypatch.setattr(graphrag, "check_output", lambda a, ctx: GuardrailVerdict(False, "ungrounded"))
    e = _explain()
    assert not e.grounded and "verified" in e.text.lower()

def test_collect_off_makes_one_answer_and_saves_nothing(tutor, monkeypatch):
    monkeypatch.setattr(graphrag.settings, "dpo_collect", False)
    assert _explain().text == "good answer" and tutor == []


# --- offline collection from the pairwise judge ---

@pytest.mark.parametrize("verdict, expected", [
    ("A", [("q", ["new"], ["old"], "eval_pairwise")]),
    ("B", [("q", ["old"], ["new"], "eval_pairwise")]),
    ("TIE", []),
])
def test_pairwise_eval_saves_winner_and_loser(verdict, expected, monkeypatch):
    saved = []
    monkeypatch.setattr(judge_eval, "judge_pairwise", lambda q, a, b: verdict)
    monkeypatch.setattr(judge_eval, "save_pairs", lambda db, q, chosen, rejected, source: saved.append((q, chosen, rejected, source)))
    judge_eval.run_judge_eval({}, lambda r: "new", lambda r: "old", [{"question": "q"}], db=object())
    assert saved == expected

def test_pairwise_eval_without_db_saves_nothing(monkeypatch):
    monkeypatch.setattr(judge_eval, "judge_pairwise", lambda q, a, b: "A")
    monkeypatch.setattr(judge_eval, "save_pairs", lambda *a, **k: pytest.fail("should not save"))
    assert judge_eval.run_judge_eval({}, lambda r: "new", lambda r: "old", [{"question": "q"}])["win_rate"] == 1.0
