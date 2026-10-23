import httpx
import pytest
from pydantic import ValidationError
from eval.runners import judge_eval_jev as je

@pytest.fixture
def jev(monkeypatch):
    monkeypatch.setattr(je.settings, "jev_url", "https://jev.test/decide")
    monkeypatch.setattr(je.settings, "jev_api_key", "k")
    def use(handler):
        def post(url, **kw):
            with httpx.Client(transport=httpx.MockTransport(handler)) as c:
                return c.post(url, **kw)
        monkeypatch.setattr(je.httpx, "post", post)
    return use

def _reply(choice):
    other = "B" if choice == "A" else "A"
    return httpx.Response(200, json={"decision": choice, "probabilities": {choice: 0.9, other: 0.1}})

@pytest.mark.parametrize("decisions, verdict", [(["A", "B"], "A"), (["B", "A"], "B"), (["A", "A"], "TIE")])
def test_pairwise_swaps_order_and_votes(jev, decisions, verdict):
    replies = iter(decisions)
    jev(lambda req: _reply(next(replies)))
    assert je.judge_pairwise("q", "a", "b") == verdict

def test_run_judge_eval_win_rate(jev):
    replies = iter(["A", "B", "A", "A"])  # row 1: candidate wins, row 2: tie
    jev(lambda req: _reply(next(replies)))
    rows = [{"question": "q1"}, {"question": "q2"}]
    assert je.run_judge_eval({}, lambda r: "cand", lambda r: "base", rows) == {"win_rate": 0.75, "n": 2}

def test_unknown_decision_is_rejected(jev):
    jev(lambda req: httpx.Response(200, json={"decision": "C", "probabilities": {"A": 0.5, "B": 0.5}}))
    with pytest.raises(ValidationError):
        je.judge_pairwise("q", "a", "b")

def test_without_url_is_a_config_error(monkeypatch):
    monkeypatch.setattr(je.settings, "jev_url", "")
    with pytest.raises(RuntimeError):
        je.judge_pairwise("q", "a", "b")
