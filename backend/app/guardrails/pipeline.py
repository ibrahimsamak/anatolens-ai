import re
from dataclasses import dataclass
from app.llm.factory import get_chat_model

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

_JUDGE = ("You are a strict grounding checker. Answer only YES or NO: is EVERY factual claim in the "
          "ANSWER supported by the CONTEXT?\n\nCONTEXT:\n{ctx}\n\nANSWER:\n{ans}")


def check_input(question: str) -> GuardrailVerdict:
    if _INJECTION.search(question):
        return GuardrailVerdict(False, "prompt_injection", EDU_REDIRECT)
    if _MEDICAL_ADVICE.search(question):
        return GuardrailVerdict(False, "medical_advice", EDU_REDIRECT)
    return GuardrailVerdict(True)

def check_output(answer: str, context: str) -> GuardrailVerdict:
    if not context.strip():
        return GuardrailVerdict(False, "no_context")
    verdict = get_chat_model().invoke(_JUDGE.format(ctx=context, ans=answer)).content.strip().upper()
    
    if not verdict.startswith("YES"):
        return GuardrailVerdict(False, "ungrounded")
    return GuardrailVerdict(True)

