import asyncio
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from app.agents import mcp_tools
from app.agents.mcp_tools import KnowledgeServiceUnavailable, KnowledgeToolError
from app.mcp_server import anatomy_server
from app.mcp_server.anatomy_server import search_knowledge, get_structure, graph_neighbors, get_quiz_bank
from app.rag import graphrag
from app.rl.reranker import Reranker


def test_server_exposes_the_four_tools():
    async def names():
        async with Client(anatomy_server.mcp) as c:
            return {t.name for t in await c.list_tools()}
    assert asyncio.run(names()) == {"search_knowledge", "get_structure", "graph_neighbors", "get_quiz_bank"}

def test_search_needs_a_scope():
    with pytest.raises(ToolError):
        search_knowledge("anything")


# --- client side: server down / tool errors ---

def test_server_that_cannot_start_is_reported_clearly(monkeypatch):
    monkeypatch.setattr(mcp_tools, "connections", lambda: {"anatomy": {
        "command": "definitely-not-a-real-command-xyz", "args": [], "transport": "stdio"}})
    with pytest.raises(KnowledgeServiceUnavailable):
        mcp_tools.search_knowledge_via_mcp(["spine.lumbar_region"], "q", "en")

def test_results_come_back_with_the_retriever_shape(monkeypatch):
    async def fake(name, args):
        assert name == "search_knowledge" and args["structure_ids"] == ["spine.lumbar_region"]
        return [{"text": "Five vertebrae.", "source": "Gray's", "structure_id": "spine.lumbar_region"}]
    monkeypatch.setattr(mcp_tools, "call_tool", fake)
    [c] = mcp_tools.search_knowledge_via_mcp(["spine.lumbar_region"], "q", "en")
    assert (c.text, c.source) == ("Five vertebrae.", "Gray's")


class Graph:
    def neighbors(self, sid, hops): return []

@pytest.fixture
def mcp_tutor(monkeypatch):
    monkeypatch.setattr(graphrag.settings, "knowledge_source", "mcp")
    monkeypatch.setattr(graphrag, "get_cache", lambda: None)
    monkeypatch.setattr(graphrag, "get_reranker", lambda: Reranker())
    monkeypatch.setattr(graphrag, "invoke_with_fallback", lambda *a, **k: pytest.fail("must not answer without knowledge"))
    return monkeypatch

def _explain():
    return graphrag.explain_structure("spine.lumbar_region", "what does it do?", "en", None, Graph())

def test_tutor_says_service_unavailable_when_mcp_is_down(mcp_tutor):
    def down(*a): raise KnowledgeServiceUnavailable("down")
    mcp_tutor.setattr(graphrag, "search_knowledge_via_mcp", down)
    e = _explain()
    assert not e.grounded and "unavailable" in e.text.lower()

def test_tutor_treats_rejected_ids_as_no_knowledge(mcp_tutor):
    def rejected(*a): raise KnowledgeToolError("unknown structure_id")
    mcp_tutor.setattr(graphrag, "search_knowledge_via_mcp", rejected)
    e = _explain()
    assert not e.grounded and "verified" in e.text.lower()


# --- against the real database ---

@pytest.mark.integration
def test_search_knowledge_tool_returns_approved_only():
    res = search_knowledge("lumbar function", lesson_id="spine_001", locale="en")
    assert res and all("coccygeal" not in r["structure_id"] for r in res)  # draft excluded

@pytest.mark.integration
def test_unknown_ids_are_rejected():
    for call in (lambda: get_structure("spine.made_up"), lambda: graph_neighbors("spine.made_up"),
                 lambda: search_knowledge("q", structure_ids=["spine.made_up"]),
                 lambda: search_knowledge("q", lesson_id="spine_001", structure_ids=["heart.aorta"]),
                 lambda: get_quiz_bank("no_such_lesson")):
        with pytest.raises(ToolError):
            call()

@pytest.mark.integration
def test_quiz_bank_is_approved_only():
    from app.db.session import SessionLocal
    from app.models.learning import QuizQuestion
    with SessionLocal() as db:
        approved = {q.id for q in db.query(QuizQuestion).filter_by(lesson_id="spine_001", review_status="APPROVED")}
    assert {q["id"] for q in get_quiz_bank("spine_001", limit=100)} <= approved

@pytest.mark.integration
def test_real_stdio_server_end_to_end():
    s = asyncio.run(mcp_tools.call_tool("get_structure", {"structure_id": "heart.left_ventricle"}))
    assert s["lesson_id"] == "heart_001"
    tools = asyncio.run(mcp_tools.load_mcp_tools())
    assert {t.name for t in tools} >= {"search_knowledge", "get_quiz_bank"}
