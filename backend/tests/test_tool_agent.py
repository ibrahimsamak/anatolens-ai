import sys
from types import SimpleNamespace
import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from app.agents import tool_agent
from app.agents.mcp_tools import KnowledgeServiceUnavailable
from app.guardrails.pipeline import GuardrailVerdict
from app.rag import graphrag
from app.rl.reranker import Reranker

TOY_SERVER = '''
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
mcp = FastMCP("toy")

@mcp.tool()
def get_structure(structure_id: str) -> dict:
    """structure"""
    if structure_id != "spine.lumbar_region":
        raise ToolError(f"unknown structure_id {structure_id!r}")
    return {"id": structure_id, "lesson_id": "spine_001", "name_en": "Lumbar region"}

@mcp.tool()
def search_knowledge(query: str, structure_ids: list[str] | None = None) -> list[dict]:
    """search"""
    return [{"text": "The lumbar region has five vertebrae.", "source": "Gray's", "structure_id": "spine.lumbar_region"}]

if __name__ == "__main__":
    mcp.run(show_banner=False)
'''


class FakeLLM(GenericFakeChatModel):
    def bind_tools(self, tools, **kw):
        return self


def _call(name, args, i):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"c{i}", "type": "tool_call"}])


@pytest.fixture
def toy(monkeypatch, tmp_path):
    server = tmp_path / "toy_server.py"
    server.write_text(TOY_SERVER, encoding="utf-8")
    monkeypatch.setattr(tool_agent, "_client", lambda: MultiServerMCPClient(
        {"anatomy": {"command": sys.executable, "args": [str(server)], "transport": "stdio"}}))
    def script(*messages):
        monkeypatch.setattr(tool_agent, "init_chat_model", lambda *a, **k: FakeLLM(messages=iter(messages)))
    return script


def test_agent_uses_tools_and_returns_the_knowledge_it_saw(toy):
    toy(_call("get_structure", {"structure_id": "spine.lumbar_region"}, 1),
        _call("search_knowledge", {"query": "function", "structure_ids": ["spine.lumbar_region"]}, 2),
        AIMessage(content="It has five vertebrae [1]."))
    answer, chunks = tool_agent.run_agent("spine.lumbar_region", "what does it do?", "en")
    assert answer == "It has five vertebrae [1]."
    assert [(c.text, c.source) for c in chunks] == [("The lumbar region has five vertebrae.", "Gray's")]

def test_tool_error_is_shown_to_the_agent_not_raised(toy):
    toy(_call("get_structure", {"structure_id": "spine.made_up"}, 1),
        AIMessage(content="I have no verified information."))
    answer, chunks = tool_agent.run_agent("spine.made_up", "q", "en")
    assert chunks == [] and "no verified" in answer

def test_agent_answering_from_memory_returns_no_knowledge(toy):
    toy(AIMessage(content="The lumbar spine has seven vertebrae."))   # never called search_knowledge
    assert tool_agent.run_agent("spine.lumbar_region", "q", "en")[1] == []

def test_step_limit_returns_nothing_instead_of_crashing(toy, monkeypatch):
    monkeypatch.setattr(tool_agent.settings, "agent_max_steps", 1)
    toy(*[_call("get_structure", {"structure_id": "spine.lumbar_region"}, i) for i in range(10)])
    assert tool_agent.run_agent("spine.lumbar_region", "q", "en") == ("", [])

def test_server_that_cannot_start_is_service_unavailable(monkeypatch):
    monkeypatch.setattr(tool_agent, "_client", lambda: MultiServerMCPClient(
        {"anatomy": {"command": "definitely-not-a-real-command-xyz", "args": [], "transport": "stdio"}}))
    with pytest.raises(KnowledgeServiceUnavailable):
        tool_agent.run_agent("spine.lumbar_region", "q", "en")


def test_chunks_skip_errors_other_tools_and_duplicates():
    row = {"text": "t", "source": "s", "structure_id": "x"}
    art = {"structured_content": {"result": [row, row]}}
    msgs = [ToolMessage("", tool_call_id="1", name="search_knowledge", artifact=art),
            ToolMessage("", tool_call_id="2", name="search_knowledge", artifact=art, status="error"),
            ToolMessage("", tool_call_id="3", name="graph_neighbors", artifact={"structured_content": {"result": ["y"]}}),
            AIMessage(content="done")]
    assert [c.text for c in tool_agent._chunks(msgs)] == ["t"]



class Graph:
    def neighbors(self, sid, hops): return []

@pytest.fixture
def agent_mode(monkeypatch):
    monkeypatch.setattr(graphrag.settings, "tutor_mode", "agent")
    monkeypatch.setattr(graphrag.settings, "dpo_collect", False)
    monkeypatch.setattr(graphrag, "get_cache", lambda: None)
    monkeypatch.setattr(graphrag, "get_reranker", lambda: Reranker())
    monkeypatch.setattr(graphrag, "invoke_with_fallback", lambda *a, **k: pytest.fail("pipeline LLM must not run"))
    monkeypatch.setattr(graphrag, "check_output", lambda a, ctx: GuardrailVerdict("[1]" in a and "five" in ctx))
    return monkeypatch

def _explain():
    return graphrag.explain_structure("spine.lumbar_region", "what does it do?", "en", None, Graph())

CHUNK = SimpleNamespace(text="The lumbar region has five vertebrae.", source="Gray's", structure_id="spine.lumbar_region")

def test_grounded_agent_answer_is_returned_with_citations(agent_mode):
    agent_mode.setattr(graphrag, "run_agent", lambda *a: ("Five vertebrae [1].", [CHUNK]))
    e = _explain()
    assert e.grounded and e.text == "Five vertebrae [1]." and e.citations == ["Gray's"]

def test_answer_without_knowledge_is_blocked(agent_mode):
    agent_mode.setattr(graphrag, "run_agent", lambda *a: ("Seven vertebrae.", []))
    e = _explain()
    assert not e.grounded and "verified" in e.text.lower()

def test_ungrounded_agent_answer_is_blocked(agent_mode):
    agent_mode.setattr(graphrag, "run_agent", lambda *a: ("Seven vertebrae, no citation.", [CHUNK]))
    assert not _explain().grounded

def test_empty_answer_from_step_limit_is_blocked(agent_mode):
    agent_mode.setattr(graphrag, "run_agent", lambda *a: ("", []))
    assert not _explain().grounded

def test_agent_server_down_says_unavailable(agent_mode):
    def down(*a): raise KnowledgeServiceUnavailable("down")
    agent_mode.setattr(graphrag, "run_agent", down)
    e = _explain()
    assert not e.grounded and "unavailable" in e.text.lower()
