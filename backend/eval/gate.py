import subprocess, sys
from pathlib import Path
import yaml
from pydantic import BaseModel
import mlflow

from app.core.config import settings
from app.db.session import SessionLocal
from app.graph.anatomy_graph import build_graph
from eval.runners.guardrail_eval import run_guardrail_eval
from eval.runners.rag_eval import run_rag_eval
from eval.runners.recognition_eval import run_recognition_eval
from eval.runners.rl_eval import run_rl_eval


class EvalConfig(BaseModel):
    chat_model: str; embedding_model: str
    datasets: dict[str, str]; thresholds: dict[str, float]
    cost_per_1k: dict; mlflow_enabled: bool = True; langsmith_enabled: bool = False
    rl_min_scored: int = 50


def load_eval_config(path: str = "eval/config.yaml") -> EvalConfig:
    return EvalConfig(**yaml.safe_load(open(path)))


RAG_METRICS = ("faithfulness", "answer_relevancy", "context_recall")

def _git_sha() -> str:
    try: return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().strip()
    except Exception: return "unknown"

def _prefixed(prefix: str, res: dict, keep=()) -> dict:
    return {k if k in keep else f"{prefix}_{k}": v for k, v in res.items()}

def compare_to_thresholds(metrics: dict, thresholds: dict, skipped: dict[str, str] | None = None) -> tuple[bool, list[str]]:
    skipped = skipped or {}
    failures = []
    for name, floor in thresholds.items():
        if name in skipped:
            continue
        val = metrics.get(name)
        if val is None:
            failures.append(f"{name}: MISSING"); continue
        if val < floor:
            failures.append(f"{name}: {val:.3f} < {floor}")
    return (len(failures) == 0, failures)


def run_all(cfg: EvalConfig) -> tuple[dict, dict[str, str]]:
    m, skipped = {}, {"judge_win_rate": "needs candidate/baseline answer sets; run eval.runners.judge_eval directly"}
    with SessionLocal() as db:
        if settings.openai_api_key:
            graph = build_graph(*map(str, sorted(Path("../content").glob("*/structures.yaml"))))
            m |= _prefixed("rag", run_rag_eval(cfg, db, graph), keep=RAG_METRICS)
        else:
            skipped |= {k: "OPENAI_API_KEY not set" for k in RAG_METRICS}
        m |= _prefixed("guardrail", run_guardrail_eval(cfg))
        m |= _prefixed("recognition", run_recognition_eval(cfg, db))
        m |= _prefixed("rl", run_rl_eval(cfg, db))
    if m["rl_n"] < cfg.rl_min_scored:
        skipped["rl_uplift_vs_logged"] = f"only {m['rl_n']} scored events (< {cfg.rl_min_scored})"
    return m, skipped


def _log_mlflow(cfg: EvalConfig, metrics: dict, skipped: dict[str, str]) -> None:
    with mlflow.start_run():
        mlflow.log_params({"git_sha": _git_sha(), "model": cfg.chat_model})
        mlflow.log_metrics({k: float(v) for k, v in metrics.items() if isinstance(v, (int, float))})
        mlflow.set_tags({f"skipped.{k}": v for k, v in skipped.items()})


def main() -> None:
    cfg = load_eval_config("eval/config.yaml")
    metrics, skipped = run_all(cfg)
    if cfg.mlflow_enabled:
        _log_mlflow(cfg, metrics, skipped)
    ok, failures = compare_to_thresholds(metrics, cfg.thresholds, skipped)
    print("METRICS:", metrics)
    for name, reason in skipped.items():
        print(f"SKIPPED {name}: {reason}")
    print("FAILURES:", failures)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
