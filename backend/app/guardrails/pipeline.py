import re
from dataclasses import dataclass
import httpx
from app.core.config import settings
from app.guardrails.judge import grounded_probability

@dataclass
class GuardrailVerdict:
    allowed: bool
    reason: str = ""
    redirect: str | None = None

_MEDICAL_ADVICE = re.compile(
    r"\b(diagnos\w*|prescri\w*|medications?|dosage|treat\w*|should i take|is it cancer)\b", re.I)
_INJECTION = re.compile(
    r"\bignore\b(\s+\w+){0,3}\s+(instructions|rules)\b|\bsystem prompt\b|\bjailbreak\b", re.I)

EDU_REDIRECT = ("I can only help with educational anatomy explanations, not medical advice. "
                "Please consult a clinician. Would you like to learn how this structure works?")


def check_input(question: str) -> GuardrailVerdict:
    if _INJECTION.search(question):
        return GuardrailVerdict(False, "prompt_injection", EDU_REDIRECT)
    if _MEDICAL_ADVICE.search(question):
        return GuardrailVerdict(False, "medical_advice", EDU_REDIRECT)
    return GuardrailVerdict(True)

def check_output(answer: str, context: str) -> GuardrailVerdict:
    if not context.strip():
        return GuardrailVerdict(False, "no_context")
    try:
        p = grounded_probability(answer, context)
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        return GuardrailVerdict(False, "judge_unavailable")
    if p < settings.judge_threshold:
        return GuardrailVerdict(False, "ungrounded")
    return GuardrailVerdict(True)
