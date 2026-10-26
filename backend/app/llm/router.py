import re
from pathlib import Path
import structlog
import yaml
from langchain.chat_models import init_chat_model
from opentelemetry import trace
from app.obs.cost import CostCallback
from app.obs.metrics import LLM_FALLBACKS

_CFG = yaml.safe_load(open(Path(__file__).resolve().parents[2] / "eval" / "config.yaml"))["routing"]
_REASONING = re.compile(r"\b(" + "|".join(map(re.escape, _CFG["reasoning_keywords"])) + r")\w*", re.I)
log = structlog.get_logger()

def cheap_model() -> str:
    return _CFG["cheap"]

def route_model(question: str, structure_id: str)-> str:
    return _CFG["strong"] if _REASONING.search(question or "") else _CFG["cheap"]

def _invoke(model: str, prompt, temperature: float = 0) -> str:
    trace.get_current_span().set_attribute("llm.model", model)
    return init_chat_model(model, temperature=temperature, callbacks=[CostCallback(model)]).invoke(prompt).content

def invoke_with_fallback(prompt, primary: str, fallback:str, temperature: float = 0)-> str:
    try:
        return _invoke(primary, prompt, temperature)
    except Exception as e:
        if fallback == primary:
            raise
        log.warning("llm_fallback", primary=primary, fallback=fallback, error=type(e).__name__)
        LLM_FALLBACKS.labels(primary=primary).inc()
        return _invoke(fallback, prompt, temperature)
