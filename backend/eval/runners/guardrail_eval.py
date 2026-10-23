import json
from app.guardrails.pipeline import check_input

def run_guardrail_eval(cfg) -> dict:
    rows = [json.loads(l) for l in open(cfg.datasets["redteam"])]
    unsafe = [r for r in rows if r["must_refuse"]]
    refused = sum(1 for r in unsafe if not check_input(r["prompt"]).allowed)
    false_block = sum(1 for r in rows if not r["must_refuse"] and not check_input(r["prompt"]).allowed)
    return {
        "refusal_rate": refused / len(unsafe) if unsafe else 1.0,
        "false_block": false_block, "n": len(rows)
        }