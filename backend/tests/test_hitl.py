import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from app.agents.authoring_graph import build_authoring_graph

DRAFT = "The lumbar region has five vertebrae that carry most of the body's weight."

def make(saver, persisted):
    return build_authoring_graph(saver, model=FakeListChatModel(responses=[DRAFT]),
                                 persist=lambda s: persisted.append(s) or "chunk-1")

def start(graph, thread_id="lesson-x"):
    cfg = {"configurable": {"thread_id": thread_id}}
    out = graph.invoke({"lesson_id": "spine_001", "structure_id": "spine.lumbar_region"}, cfg)
    return cfg, out

def test_authoring_pauses_then_resumes_on_approval():
    saver, persisted = InMemorySaver(), []
    cfg, out = start(make(saver, persisted))
    assert out["__interrupt__"][0].value["draft_text"] == DRAFT   # paused at MEDICAL_REVIEW
    assert out["status"] == "MEDICAL_REVIEW" and not persisted   # nothing retrievable yet
    # simulate a fresh process reusing the same checkpointer/thread_id:
    final = make(saver, persisted).invoke(Command(resume={"decision": "approve", "reviewer": "r@x.com"}), cfg)
    assert final["status"] == "APPROVED" and final["chunk_id"] == "chunk-1"
    assert persisted[0]["draft_text"] == DRAFT and persisted[0]["reviewer"] == "r@x.com"

def test_reject_returns_to_content_review_and_persists_nothing():
    saver, persisted = InMemorySaver(), []
    graph = make(saver, persisted)
    cfg, _ = start(graph)
    final = graph.invoke(Command(resume={"decision": "reject", "notes": "too vague"}), cfg)
    assert final["status"] == "CONTENT_REVIEW" and final["notes"] == "too vague"
    assert not persisted

def test_invalid_decision_keeps_review_pending():
    saver, persisted = InMemorySaver(), []
    graph = make(saver, persisted)
    cfg, _ = start(graph)
    with pytest.raises(ValueError):
        graph.invoke(Command(resume={"decision": "publish"}), cfg)
    assert graph.get_state(cfg).next == ("medical_review",)   # still waiting for a human
    assert not persisted
