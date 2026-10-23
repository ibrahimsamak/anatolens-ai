import pytest
from prometheus_client import REGISTRY
from app.llm.router import route_model, invoke_with_fallback

def test_simple_lookup_uses_cheap_tier():
    assert "mini" in route_model("how many lumbar vertebrae?", "spine.lumbar_region").lower()

def test_reasoning_question_uses_strong_tier():
    m = route_model("explain why lumbar lordosis affects weight distribution clinically", "spine.lumbar_region")
    assert "mini" not in m.lower()

@pytest.mark.parametrize("q", ["Explains the curve", "How does it COMPARE to cervical?", "Why?"])
def test_keywords_match_whole_words_any_case(q):
    assert "mini" not in route_model(q, "s").lower()

@pytest.mark.parametrize("q", ["anywhy, list the bones", "", None])
def test_keyword_inside_another_word_or_empty_stays_cheap(q):
    assert "mini" in route_model(q, "s").lower()

def _fake_models(monkeypatch, fail=()):
    import app.llm.router as R
    calls = []
    def fake(model, **k):
        assert k["callbacks"][0].model == model   
        class M:
            def invoke(self, msgs):
                calls.append(model)
                if model in fail: raise RuntimeError("down")
                class R2: content = "ok"
                return R2()
        return M()
    monkeypatch.setattr(R, "init_chat_model", fake)
    return calls

def test_fallback_on_primary_error(monkeypatch):
    calls = _fake_models(monkeypatch, fail={"primary:x"})
    before = REGISTRY.get_sample_value("anatolens_llm_fallback_total", {"primary": "primary:x"}) or 0.0
    assert invoke_with_fallback("q", "primary:x", "fallback:y") == "ok" and calls == ["primary:x", "fallback:y"]
    assert REGISTRY.get_sample_value("anatolens_llm_fallback_total", {"primary": "primary:x"}) == before + 1

def test_no_retry_when_fallback_is_the_same_model(monkeypatch):
    calls = _fake_models(monkeypatch, fail={"cheap:x"})
    with pytest.raises(RuntimeError):
        invoke_with_fallback("q", "cheap:x", "cheap:x")
    assert calls == ["cheap:x"]

def test_strong_tier_has_pricing():
    from app.obs.cost import _PRICING
    from app.llm.router import _CFG
    assert {_CFG["cheap"], _CFG["strong"]} <= set(_PRICING)
