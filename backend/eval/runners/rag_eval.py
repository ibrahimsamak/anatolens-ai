import json
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_recall
from app.rag.graphrag import explain_structure
from app.rag.retriever import retrieve_chunks
from app.llm.router import route_model, cheap_model
from app.obs.metrics import LLM_FALLBACKS

def _fallbacks() -> float:
    return sum(s.value for m in LLM_FALLBACKS.collect() for s in m.samples if s.name.endswith("_total"))

def run_rag_eval(cfg, db, graph)->dict:
    rows = [json.loads(l) for l in open(cfg.datasets["rag"])]
    records = []
    unanswerable = 0
    routed = {"cheap": 0, "strong": 0}
    fallbacks_before = _fallbacks()
    for r in rows:
        seed = [r["structure_id"], *graph.neighbors(r["structure_id"], 1)]
        ctx = [c.text for c in retrieve_chunks(seed, r["question"], "en", db)]
        if not ctx:
            unanswerable += 1
            continue
        e = explain_structure(r["structure_id"], r["question"], "en", db, graph, use_cache=False)
        records.append({"question": r["question"], "answer": e.text, "contexts": ctx, "ground_truth": r["gold"]})
        routed["cheap" if route_model(r["question"], r["structure_id"]) == cheap_model() else "strong"] += 1
    tiers = {"routed_cheap": routed["cheap"], "routed_strong": routed["strong"], "fallbacks": int(_fallbacks() - fallbacks_before)}
    if not records:
        return {"faithfulness": 0.0, "answer_relevancy": 0.0, "context_recall": 0.0,
                "n": 0, "unanswerable": unanswerable, **tiers}
    ds = Dataset.from_list(records)
    scores = evaluate(ds, metrics=[faithfulness, answer_relevancy, context_recall])
    return {
            "faithfulness": float(scores["faithfulness"]),
            "answer_relevancy": float(scores["answer_relevancy"]),
            "context_recall": float(scores["context_recall"]),
            "n": len(records), 
            "unanswerable": unanswerable,
            **tiers
    }