import importlib
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from prometheus_client import REGISTRY
from app.guardrails.pipeline import check_input
from app.obs import cost
from app.obs.cost import CostCallback, track_cost
from app.obs.metrics import GUARDRAIL_TRIGGERS

def _value(name, **labels):
    return REGISTRY.get_sample_value(name, labels) or 0.0

def test_guardrail_counter_labels_are_bounded():
    # labelnames must be a small fixed set, never 'question'
    assert set(GUARDRAIL_TRIGGERS._labelnames) == {"reason"}

def test_cost_computation():
    assert track_cost("openai:gpt-4o-mini", 1000, 1000) > 0

def test_guardrail_block_is_counted():
    before = _value("anatolens_guardrail_total", reason="medical_advice")
    assert not check_input("Prescribe medication for my back.").allowed
    assert _value("anatolens_guardrail_total", reason="medical_advice") == before + 1

def test_latency_uses_route_template_not_raw_path():
    from app.main import app
    c = TestClient(app)
    c.get("/healthz"); c.get("/no/such/path/123")
    assert _value("anatolens_request_seconds_count", route="/healthz") >= 1
    assert _value("anatolens_request_seconds_count", route="unmatched") >= 1
    assert _value("anatolens_request_seconds_count", route="/no/such/path/123") == 0
    body = c.get("/metrics/").text
    assert "anatolens_request_seconds" in body and "anatolens_guardrail_total" in body

def test_llm_calls_feed_token_cost():
    before = _value("anatolens_token_cost_usd_total", model="openai:gpt-4o-mini")
    msg = AIMessage("ok", usage_metadata={"input_tokens": 1000, "output_tokens": 1000, "total_tokens": 2000})
    CostCallback("openai:gpt-4o-mini").on_llm_end(LLMResult(generations=[[ChatGeneration(message=msg)]]))
    # 1k input @ 0.00015 + 1k output @ 0.0006
    assert _value("anatolens_token_cost_usd_total", model="openai:gpt-4o-mini") - before == pytest.approx(0.00075)

def test_pricing_loads_from_any_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert "openai:gpt-4o-mini" in importlib.reload(cost)._PRICING
