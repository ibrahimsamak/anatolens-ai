from dataclasses import dataclass
from app.rag.retriever import retrieve_chunks
from app.llm.factory import get_chat_model
from app.guardrails.pipeline import check_output


from dataclasses import dataclass
from app.rag.retriever import retrieve_chunks
from app.llm.factory import get_chat_model
from app.guardrails.pipeline import check_output

NO_INFO = {"en": "I don't have verified information about that yet. Please ask your instructor.",
           "ar": "لا تتوفر لديّ معلومات موثّقة عن ذلك بعد. يرجى سؤال المدرّس."}

@dataclass
class Explanation:
    text: str; citations: list[str]; grounded: bool
    
_PROMPT = ("You are an anatomy tutor for students. Answer in {locale}. Use ONLY the context. "
           "Cite sources inline as [n]. Keep it clear and student-friendly.\n\n"
           "CONTEXT:\n{ctx}\n\nQUESTION: {q}")


def explain_structure(structure_id, question, locale, db, graph) -> Explanation:
    seed = [structure_id, *graph.neighbors(structure_id, hops=1)]
    chunks = retrieve_chunks(seed, question or "overview", locale, db)
    if not chunks:
        return Explanation(NO_INFO.get(locale, NO_INFO["en"]), [], False)
    ctx = "\n".join(f"[{i+1}] {c.text} (src: {c.source})" for i, c in enumerate(chunks))
    answer = get_chat_model().invoke(
        _PROMPT.format(locale=locale, ctx = ctx, q=question or "Give an overview")
    ).content
    verdict = check_output(answer, ctx)
    if not verdict.allowed:
        return Explanation(NO_INFO.get(locale, NO_INFO["en"]), [], False)
    return Explanation(answer, [c.source for c in chunks], True)

