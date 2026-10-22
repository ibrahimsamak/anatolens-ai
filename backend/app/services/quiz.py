import uuid, json
from sqlalchemy import select
from app.models.content import KnowledgeChunk
from app.models.learning import QuizQuestion
from app.llm.factory import get_chat_model

_GEN = ('From the APPROVED context only, write ONE {difficulty} multiple-choice anatomy question. '
        'Return JSON: {{"prompt":...,"choices":[4 strings],"correct":"<one of choices>"}}.\n\n'
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
    out = []
    for _ in range(n):
        raw = get_chat_model().invoke(_GEN.format(difficulty=difficulty, ctx=ctx)).content
        data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        if data["correct"] not in data["choices"]:
            continue
        q = QuizQuestion(id=str(uuid.uuid4()), lesson_id=lesson_id, structure_id=structure_id,
                         difficulty=difficulty, prompt=data["prompt"], correct=data["correct"],
                         choices=data["choices"], review_status="APPROVED")
        db.add(q); out.append(q)
    db.commit()
    return out

def grade(question_id: str, answer: str, db) -> bool:
    q = db.get(QuizQuestion, question_id)
    if not q:
        raise KeyError(question_id)
    return answer.strip() == q.correct.strip()
