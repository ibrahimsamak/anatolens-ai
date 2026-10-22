import pytest
from app.services.quiz import generate_questions, grade
from app.db.session import SessionLocal

@pytest.mark.integration
def test_generate_from_approved_lumbar_content():
    with SessionLocal() as db:
        qs = generate_questions("spine_001", "spine.lumbar_region", "medium", db, n=1)
        assert qs and qs[0].correct in qs[0].choices
        assert grade(qs[0].id, qs[0].correct, db)

@pytest.mark.integration
def test_structure_without_approved_content_yields_nothing():
    with SessionLocal() as db:
        assert generate_questions("spine_001", "spine.coccygeal_region", "easy", db) == []

@pytest.mark.integration
def test_grade_unknown_question_raises():
    with SessionLocal() as db, pytest.raises(KeyError):
        grade("nope", "x", db)
