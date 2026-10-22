import httpx
import pytest
from langchain_core.exceptions import OutputParserException
from app.guardrails import judge
from app.schemas.judge import GroundingVerdict

class FakeWriter:
    def __init__(self, reply): self.reply, self.prompts = reply, []
    def invoke(self, prompt):
        self.prompts.append(prompt)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply

class FakeModel:
    def __init__(self, reply): self.writer, self.schema = FakeWriter(reply), None
    def with_structured_output(self, schema, **kwargs):
        self.schema = schema
        return self.writer

@pytest.fixture
def backend(monkeypatch):
    def use(name, **extra):
        monkeypatch.setattr(judge.settings, "judge_backend", name)
        for k, v in extra.items():
            monkeypatch.setattr(judge.settings, k, v)
    return use

def test_llm_is_the_default_backend():
    assert type(judge.settings).model_fields["judge_backend"].default == "llm"

@pytest.mark.parametrize("grounded, p", [(True, 1.0), (False, 0.0)])
def test_llm_backend_uses_structured_output(monkeypatch, backend, grounded, p):
    backend("llm")
    model = FakeModel(GroundingVerdict(grounded=grounded))
    monkeypatch.setattr(judge, "get_chat_model", lambda: model)
    assert judge.grounded_probability("five vertebrae", "L1-L5") == p
    assert model.schema is GroundingVerdict
    assert "L1-L5" in model.writer.prompts[0] and "five vertebrae" in model.writer.prompts[0]

@pytest.mark.parametrize("reply", [OutputParserException("not json"), None])
def test_llm_backend_bad_reply_counts_as_ungrounded(monkeypatch, backend, reply):
    backend("llm")
    monkeypatch.setattr(judge, "get_chat_model", lambda: FakeModel(reply))
    assert judge.grounded_probability("a", "c") == 0.0

def _jev(handler):
    def post(url, **kw):
        with httpx.Client(transport=httpx.MockTransport(handler)) as c:
            return c.post(url, **kw)
    return post

def test_jev_backend_returns_grounded_probability(monkeypatch, backend):
    backend("jev", jev_url="https://jev.test/decide", jev_api_key="k")
    seen = {}
    def handler(req):
        seen["auth"], seen["body"] = req.headers["Authorization"], req.content.decode()
        return httpx.Response(200, json={"decision": "grounded", "probabilities": {"grounded": 0.83, "ungrounded": 0.17}})
    monkeypatch.setattr(judge.httpx, "post", _jev(handler))
    monkeypatch.setattr(judge, "get_chat_model", lambda: pytest.fail("llm must not be called"))
    assert judge.grounded_probability("five vertebrae", "L1-L5") == 0.83
    assert seen["auth"] == "Bearer k" and "L1-L5" in seen["body"] and "five vertebrae" in seen["body"]

def test_jev_http_error_raises(monkeypatch, backend):
    backend("jev", jev_url="https://jev.test/decide")
    monkeypatch.setattr(judge.httpx, "post", _jev(lambda req: httpx.Response(503)))
    with pytest.raises(httpx.HTTPStatusError):
        judge.grounded_probability("a", "c")

def test_jev_without_url_is_a_config_error(backend):
    backend("jev", jev_url="")
    with pytest.raises(RuntimeError):
        judge.grounded_probability("a", "c")
