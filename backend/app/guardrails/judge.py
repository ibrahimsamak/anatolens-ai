import httpx
from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError
from app.core.config import settings
from app.llm.factory import get_chat_model
from app.schemas.judge import GroundingVerdict

_JUDGE = ("You are a strict grounding checker. Decide whether EVERY factual claim in the ANSWER "
          "is supported by the CONTEXT.\n\nCONTEXT:\n{ctx}\n\nANSWER:\n{ans}")

_JEV_QUESTION = "Is every factual claim in the ANSWER supported by the CONTEXT?"

def _llm_grounded(answer: str, context: str) -> float:
    try:
        v = get_chat_model().with_structured_output(GroundingVerdict).invoke(_JUDGE.format(ctx=context, ans=answer))
    except (ValidationError, OutputParserException):
        return 0.0
    return 1.0 if v is not None and v.grounded else 0.0

def _jev_grounded(answer: str, context: str) -> float:
    if not settings.jev_url:
        raise RuntimeError("JUDGE_BACKEND=jev but JEV_URL is not set")
    r = httpx.post(settings.jev_url, timeout=settings.jev_timeout,
                   headers={"Authorization": f"Bearer {settings.jev_api_key}"},
                   json={"question": _JEV_QUESTION, "options": ["grounded", "ungrounded"],
                         "inputs": {"context": context, "answer": answer}})
    r.raise_for_status()
    return float(r.json()["probabilities"]["grounded"])

_BACKENDS = {"llm": _llm_grounded, "jev": _jev_grounded}

def grounded_probability(answer: str, context: str) -> float:
    return _BACKENDS[settings.judge_backend](answer, context)
