import json
from app.llm.factory import get_chat_model

_RUBRIC = ("Judge which anatomy answer is more accurate, grounded, and student-friendly. "
           "Reply with exactly 'A' or 'B'.\nQUESTION: {q}\n\nA:\n{a}\n\nB:\n{b}")


def _ask_judge(q, a, b) -> str:
    out = get_chat_model().invoke(_RUBRIC.format(q=q, a=a, b=b)).content.strip().upper()
    return "A" if out.startswith("A") else "B"


def judge_pairwise(question, answer_a, answer_b)->str:
    first = _ask_judge(question, answer_a, answer_b)
    second = _ask_judge(question, answer_b, answer_a)
    
    a_vode = (first == "A") + (second == "B")
    if a_vode == 2: return "A"
    if a_vode == 0: return "B"
    return "TIE"

def run_judge_eval(cfg, candidate_fn, baseline_fn, rows) -> dict:
    wins = n = 0
    for r in rows:
        res = judge_pairwise(r["question"], candidate_fn(r), baseline_fn(r))
        wins += 1 if res == "A" else (0.5 if res == "TIE" else 0); n += 1
    return {"win_rate": wins / n if n else 0.0, "n": n}

