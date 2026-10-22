import uuid
from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError
from sqlalchemy import select
from app.models.content import KnowledgeChunk
from app.models.learning import QuizQuestion
from app.llm.factory import get_chat_model
from app.schemas.quiz import GeneratedQuestion

_GEN = ('From the APPROVED context only, write ONE {difficulty} multiple-choice anatomy question '
        'with exactly 4 distinct choices. The correct answer must be copied exactly from the choices.\n\n'
        'CONTEXT:\n{ctx}')

def _approved_ctx(lesson_id, structure_id, db) -> str:
    rows = db.execute(select(KnowledgeChunk).where(
        KnowledgeChunk.review_status == "APPROVED",
        KnowledgeChunk.lesson_id == lesson_id,
        KnowledgeChunk.structure_id == structure_id)).scalars().all()
    return "\n".join(c.text for c in rows)

def generate_questions(lesson_id, structure_id, difficulty, db, n=1) -> list[QuizQuestion]:
    ctx = _approved_ctx(lesson_id, structure_id, db)
    if not ctx:
        return []
    writer = get_chat_model().with_structured_output(GeneratedQuestion)
    out = []
    for _ in range(n):
        try:
            data: GeneratedQuestion | None = writer.invoke(_GEN.format(difficulty=difficulty, ctx=ctx))
        except (ValidationError, OutputParserException):
            continue
        if data is None:
            continue
        q = QuizQuestion(id=str(uuid.uuid4()), lesson_id=lesson_id, structure_id=structure_id,
                         difficulty=difficulty, prompt=data.prompt, correct=data.correct,
                         choices=data.choices, review_status="APPROVED")
        db.add(q); out.append(q)
    db.commit()
    return out

def grade(question_id: str, answer: str, db) -> bool:
    q = db.get(QuizQuestion, question_id)
    if not q:
        raise KeyError(question_id)
    return answer.strip() == q.correct.strip()
