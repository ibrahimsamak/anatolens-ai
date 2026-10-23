from typing import Callable, Iterable, Literal
import httpx
from app.core.config import settings
from app.schemas.judge import JevRequest, PairwiseDecision

Choice = Literal["A", "B"]
Verdict = Literal["A", "B", "TIE"]
Row = dict[str, str]

_JEV_QUESTION = "Which anatomy answer is more accurate, grounded, and student-friendly?"


def _ask_judge(q: str, a: str, b: str) -> Choice:
    if not settings.jev_url:
        raise RuntimeError("JEV_URL is not set")
    req = JevRequest(question=_JEV_QUESTION, options=["A", "B"], inputs={"question": q, "A": a, "B": b})
    r = httpx.post(settings.jev_url, timeout=settings.jev_timeout,
                   headers={"Authorization": f"Bearer {settings.jev_api_key}"},
                   json=req.model_dump())
    r.raise_for_status()
    return PairwiseDecision.model_validate(r.json()).decision


def judge_pairwise(question: str, answer_a: str, answer_b: str) -> Verdict:
    first = _ask_judge(question, answer_a, answer_b)
    second = _ask_judge(question, answer_b, answer_a)

    a_votes = (first == "A") + (second == "B")
    if a_votes == 2: return "A"
    if a_votes == 0: return "B"
    return "TIE"


_SCORE: dict[Verdict, float] = {"A": 1.0, "TIE": 0.5, "B": 0.0}


def run_judge_eval(cfg, candidate_fn: Callable[[Row], str], baseline_fn: Callable[[Row], str],
                   rows: Iterable[Row]) -> dict[str, float | int]:
    wins, n = 0.0, 0
    for r in rows:
        wins += _SCORE[judge_pairwise(r["question"], candidate_fn(r), baseline_fn(r))]; n += 1
    return {"win_rate": wins / n if n else 0.0, "n": n}
