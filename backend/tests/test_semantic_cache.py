import fakeredis
import pytest
from prometheus_client import REGISTRY
from app.core.config import settings
from app.guardrails.pipeline import GuardrailVerdict
from app.rag import cache as cache_mod, graphrag
from app.rag.cache import SemanticCache


@pytest.mark.integration
def test_similar_question_hits_cache():
    c = SemanticCache(settings.redis_url, threshold=0.90)
    c.put("spine.lumbar_region", "what is the lumbar region?", "en", "Five vertebrae L1-L5.", [])
    hit = c.get("spine.lumbar_region", "what's the lumbar area?", "en")   # paraphrase
    assert hit is not None and "L1-L5" in hit["answer"]

@pytest.mark.integration
def test_different_structure_namespace_isolated():
    c = SemanticCache(settings.redis_url, threshold=0.90)
    c.put("spine.lumbar_region", "q", "en", "lumbar answer", [])
    assert c.get("spine.cervical_region", "q", "en") is None


VECS = {"what is the lumbar region?": [1.0, 0.0, 0.0], "what's the lumbar area?": [0.98, 0.2, 0.0],
        "how is it innervated?": [0.0, 1.0, 0.0], "overview": [0.0, 0.0, 1.0]}

class FakeEmb:
    def __init__(self): self.calls = 0
    def embed_query(self, text):
        self.calls += 1
        return VECS[text]

@pytest.fixture
def make_cache(monkeypatch):
    server = fakeredis.FakeServer()
    def make(connected=True, **kw):
        server.connected = connected
        monkeypatch.setattr(cache_mod.redis.Redis, "from_url", staticmethod(lambda url, **k: fakeredis.FakeRedis(server=server)))
        monkeypatch.setattr(cache_mod, "get_embeddings", FakeEmb)
        return SemanticCache("redis://fake", **kw)
    return make

def _hits():
    return REGISTRY.get_sample_value("anatolens_cache_hits_total") or 0.0

def test_paraphrase_hits_and_counts(make_cache):
    c = make_cache(threshold=0.95)
    c.put("spine.lumbar_region", "what is the lumbar region?", "en", "Five vertebrae L1-L5.", ["src1"])
    before = _hits()
    assert c.get("spine.lumbar_region", "what's the lumbar area?", "en") == {"answer": "Five vertebrae L1-L5.", "citations": ["src1"]}
    assert _hits() == before + 1
    assert c.get("spine.lumbar_region", "how is it innervated?", "en") is None

def test_structure_and_locale_are_isolated(make_cache):
    c = make_cache()
    c.put("spine.lumbar_region", "what is the lumbar region?", "en", "a", [])
    assert c.get("spine.cervical_region", "what is the lumbar region?", "en") is None
    assert c.get("spine.lumbar_region", "what is the lumbar region?", "ar") is None

def test_namespace_is_bounded_and_expires(make_cache):
    c = make_cache(max_entries=3, ttl_seconds=60)
    for i in range(5):
        c.put("s", "overview", "en", f"a{i}", [])
    assert c.r.llen("sc:en:s") == 3 and 0 < c.r.ttl("sc:en:s") <= 60

def test_clear_drops_every_locale_of_a_structure(make_cache):
    c = make_cache()
    for loc in ("en", "ar"):
        c.put("s1", "overview", loc, "x", []); c.put("s2", "overview", loc, "y", [])
    c.clear(["s1"])
    assert c.get("s1", "overview", "en") is None and c.get("s1", "overview", "ar") is None
    assert c.get("s2", "overview", "en") is not None

def test_redis_down_fails_open(make_cache):
    c = make_cache(connected=False)
    c.put("s", "overview", "en", "x", [])
    c.clear(["s"])
    assert c.get("s", "overview", "en") is None


class Chunk:
    text, source = "The lumbar region has five vertebrae.", "src1"

class Graph:
    def neighbors(self, sid, hops): return []

class Model:
    def __init__(self): self.calls = 0
    def __call__(self, prompt, primary, fallback, temperature=0):
        self.calls += 1
        return "Five vertebrae [1]."

@pytest.fixture
def tutor(monkeypatch, make_cache):
    c, model = make_cache(), Model()
    monkeypatch.setattr(graphrag, "get_cache", lambda: c)
    monkeypatch.setattr(graphrag, "retrieve_chunks", lambda *a: [Chunk()])
    monkeypatch.setattr(graphrag, "invoke_with_fallback", model)
    monkeypatch.setattr(graphrag, "check_output", lambda a, ctx: GuardrailVerdict(True))
    return c, model

def test_second_similar_question_skips_the_llm(tutor):
    c, model = tutor
    first = graphrag.explain_structure("spine.lumbar_region", "what is the lumbar region?", "en", None, Graph())
    again = graphrag.explain_structure("spine.lumbar_region", "what's the lumbar area?", "en", None, Graph())
    assert model.calls == 1 and again == first and again.grounded
    assert c.emb.calls == 2   
def test_ungrounded_answer_is_not_cached(tutor, monkeypatch):
    c, _ = tutor
    monkeypatch.setattr(graphrag, "check_output", lambda a, ctx: GuardrailVerdict(False, "ungrounded"))
    graphrag.explain_structure("s", "overview", "en", None, Graph())
    assert c.r.llen("sc:en:s") == 0

def test_eval_bypasses_cache(tutor):
    c, model = tutor
    graphrag.explain_structure("s", "overview", "en", None, Graph())
    graphrag.explain_structure("s", "overview", "en", None, Graph(), use_cache=False)
    assert model.calls == 2 and c.r.llen("sc:en:s") == 1

def test_cache_can_be_disabled(monkeypatch):
    monkeypatch.setattr(settings, "semantic_cache_enabled", False)
    assert graphrag.get_cache() is None
