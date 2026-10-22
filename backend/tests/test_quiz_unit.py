import pytest
from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError
from app.schemas.quiz import GeneratedQuestion
from app.services import quiz

GOOD = {"prompt": "How many lumbar vertebrae?", "choices": ["3", "4", "5", "6"], "correct": "5"}

class FakeDB:
    def __init__(self): self.added, self.commits = [], 0
    def add(self, obj): self.added.append(obj)
    def commit(self): self.commits += 1

class FakeWriter:
    def __init__(self, replies): self.replies, self.prompts = list(replies), []
    def invoke(self, prompt):
        self.prompts.append(prompt)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return GeneratedQuestion(**reply)

class FakeModel:
    def __init__(self, writer): self.writer, self.schema, self.kwargs = writer, None, None
    def with_structured_output(self, schema, **kwargs):
        self.schema, self.kwargs = schema, kwargs
        return self.writer

@pytest.fixture
def llm(monkeypatch):
    def install(*replies):
        model = FakeModel(FakeWriter(replies))
        monkeypatch.setattr(quiz, "get_chat_model", lambda: model)
        monkeypatch.setattr(quiz, "_approved_ctx", lambda *a: "The lumbar spine has 5 vertebrae.")
        return model
    return install

def test_schema_accepts_valid_question_and_trims():
    q = GeneratedQuestion(prompt=" How many? ", choices=[" 3", "4", "5", "6"], correct="5 ")
    assert q.prompt == "How many?" and q.choices[0] == "3" and q.correct == "5"

@pytest.mark.parametrize("bad", [
    {**GOOD, "correct": "7"},
    {**GOOD, "choices": ["3", "4", "5"]},
    {**GOOD, "choices": ["3", "4", "5", "6", "7"]},
    {**GOOD, "choices": ["5", "5", "4", "6"]},
    {**GOOD, "choices": ["3", "", "5", "6"]},
    {**GOOD, "prompt": "  "},
    {"prompt": "x", "choices": ["3", "4", "5", "6"]},
])
def test_schema_rejects_invalid_questions(bad):
    with pytest.raises(ValidationError):
        GeneratedQuestion(**bad)

def test_generate_uses_structured_output_and_saves(llm):
    model = llm(GOOD)
    db = FakeDB()
    [q] = quiz.generate_questions("spine_001", "spine.lumbar_region", "medium", db)
    assert model.schema is GeneratedQuestion and model.kwargs == {}
    assert (q.prompt, q.correct, q.choices, q.difficulty) == (GOOD["prompt"], "5", GOOD["choices"], "medium")
    assert q.review_status == "APPROVED" and db.added == [q]
    assert "medium" in model.writer.prompts[0] and "5 vertebrae" in model.writer.prompts[0]

def _schema_error():
    try:
        GeneratedQuestion(**{**GOOD, "correct": "7"})
    except ValidationError as e:
        return e

def test_generate_skips_replies_that_fail_the_schema(llm):
    llm(_schema_error(), OutputParserException("not json"), GOOD)
    db = FakeDB()
    qs = quiz.generate_questions("spine_001", "spine.lumbar_region", "easy", db, n=3)
    assert len(qs) == 1 and db.added == qs

def test_other_model_errors_are_not_swallowed(llm):
    llm(RuntimeError("rate limited"))
    with pytest.raises(RuntimeError):
        quiz.generate_questions("spine_001", "spine.lumbar_region", "easy", FakeDB())

def test_no_approved_context_never_calls_the_model(monkeypatch):
    monkeypatch.setattr(quiz, "_approved_ctx", lambda *a: "")
    monkeypatch.setattr(quiz, "get_chat_model", lambda: pytest.fail("model must not be called"))
    assert quiz.generate_questions("spine_001", "spine.coccygeal_region", "easy", FakeDB()) == []
