from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import mlflow
from mlflow.entities import SpanType
from app.core.config import settings
from app.rag.retriever import retrieve_chunks
from app.rag.cache import SemanticCache
from app.llm.router import route_model, invoke_with_fallback, cheap_model
from app.guardrails.pipeline import check_output
from app.rl.reranker import get_reranker
from app.rl.dpo_collect import save_pairs

NO_INFO = {"en": "I don't have verified information about that yet. Please ask your instructor.",
           "ar": "لا تتوفر لديّ معلومات موثّقة عن ذلك بعد. يرجى سؤال المدرّس."}

@dataclass
class Explanation:
    text: str; citations: list[str]; grounded: bool

_PROMPT = ("You are an anatomy tutor for students. Answer in {locale}. Use ONLY the context. "
           "Cite sources inline as [n]. Keep it clear and student-friendly.\n\n"
           "CONTEXT:\n{ctx}\n\nQUESTION: {q}")

_cache: SemanticCache | None = None

def get_cache() -> SemanticCache | None:
    global _cache
    if not settings.semantic_cache_enabled:
        return None
    if _cache is None:
        _cache = SemanticCache(settings.redis_url, threshold=settings.semantic_cache_threshold)
    return _cache


def _candidates(prompt: str, primary: str, n: int) -> list[str]:
    temps = [0.0] + [settings.tutor_candidate_temperature] * (max(n, 1) - 1)
    gen = lambda t: invoke_with_fallback(prompt, primary=primary, fallback=cheap_model(), temperature=t)
    if len(temps) == 1:
        return [gen(0.0)]
    with ThreadPoolExecutor(max_workers=len(temps)) as pool:
        futures = [pool.submit(gen, t) for t in temps]
    out = []
    for i, f in enumerate(futures):
        try:
            c = f.result()
        except Exception:
            if i == 0:
                raise
            continue
        if c.strip() and c not in out:
            out.append(c)
    return out


def explain_structure(structure_id, question, locale, db, graph, use_cache: bool = True) -> Explanation:
    with mlflow.start_span(name="explain_structure", span_type=SpanType.CHAIN) as span:
        span.set_inputs({"structure_id": structure_id, "question": question, "locale": locale})
        e = _explain_structure(structure_id, question, locale, db, graph, use_cache)
        span.set_outputs({"text": e.text, "citations": e.citations, "grounded": e.grounded})
        return e


def _explain_structure(structure_id, question, locale, db, graph, use_cache: bool) -> Explanation:
    cache = get_cache() if use_cache else None
    vec = cache.embed(question) if cache else None
    if cache and (hit := cache.get(structure_id, question, locale, vec=vec)):
        return Explanation(hit["answer"], hit["citations"], True)
    seed = [structure_id, *graph.neighbors(structure_id, hops=1)]
    chunks = retrieve_chunks(seed, question or "overview", locale, db)
    if not chunks:
        return Explanation(NO_INFO.get(locale, NO_INFO["en"]), [], False)
    ctx = "\n".join(f"[{i+1}] {c.text} (src: {c.source})" for i, c in enumerate(chunks))
    q = question or "Give an overview"
    prompt = _PROMPT.format(locale=locale, ctx=ctx, q=q)
    reranker = get_reranker()
    n = settings.tutor_candidates if (reranker.active or settings.dpo_collect) else 1
    candidates = _candidates(prompt, route_model(question, structure_id), n)
    ranked = reranker.rank(q, candidates)
    if settings.dpo_collect and len(ranked) > 1:
        ok = {c: check_output(c, ctx).allowed for c in ranked}
        good = [c for c in ranked if ok[c]]
        bad = [c for c in ranked if not ok[c]]
        save_pairs(db, q, good[:1], bad, source="tutor")
        answer = good[0] if good else None
    else:
        answer = next((c for c in ranked if check_output(c, ctx).allowed), None)
    if answer is None:
        return Explanation(NO_INFO.get(locale, NO_INFO["en"]), [], False)
    citations = [c.source for c in chunks]
    if cache:
        cache.put(structure_id, question, locale, answer, citations, vec=vec)
    return Explanation(answer, citations, True)
