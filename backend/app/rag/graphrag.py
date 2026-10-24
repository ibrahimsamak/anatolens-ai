from dataclasses import dataclass
import mlflow
from mlflow.entities import SpanType
from app.core.config import settings
from app.rag.retriever import retrieve_chunks
from app.rag.cache import SemanticCache
from app.llm.router import route_model, invoke_with_fallback, cheap_model
from app.guardrails.pipeline import check_output

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
    answer = invoke_with_fallback(_PROMPT.format(locale=locale, ctx = ctx, q=question or "Give an overview"), primary=route_model(question, structure_id), fallback=cheap_model())
    verdict = check_output(answer, ctx)
    if not verdict.allowed:
        return Explanation(NO_INFO.get(locale, NO_INFO["en"]), [], False)
    citations = [c.source for c in chunks]
    if cache:
        cache.put(structure_id, question, locale, answer, citations, vec=vec)
    return Explanation(answer, citations, True)
