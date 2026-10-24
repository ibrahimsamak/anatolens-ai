from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from app.api.deps import get_db
from app.services.adaptive import next_question, record_result
from app.models.learning import Progress, Attempt, QuizQuestion
from app.models.content import Lesson

router = APIRouter(prefix="/api/v1")

class NextReq(BaseModel): user_id: str; lesson_id: str
class SubmitReq(BaseModel): user_id: str; question_id: str; answer: str

@router.post("/quiz/next")
def quiz_next(req: NextReq, db=Depends(get_db)):
    q = next_question(req.user_id, req.lesson_id, db)
    if not q: raise HTTPException(404, "no approved questions available")
    return {"id": q.id, "prompt": q.prompt, "choices": q.choices,
            "difficulty": q.difficulty, "structure_id": q.structure_id, "correct": q.correct}

@router.post("/quiz/submit")
def quiz_submit(req: SubmitReq, db=Depends(get_db)):
    try:
        return record_result(req.user_id, req.question_id, req.answer, db)
    except KeyError:
        raise HTTPException(404, "unknown question")

@router.get("/progress/{user_id}")
def progress(user_id: str, db=Depends(get_db)):
    rows = db.execute(select(Progress).where(Progress.user_id == user_id)).scalars().all()
    return [{"structure_id": p.structure_id, "mastery": p.mastery, "attempts": p.attempts} for p in rows]

@router.get("/history/{user_id}")
def history(user_id: str, db=Depends(get_db)):
    rows = db.execute(
        select(Attempt, QuizQuestion, Lesson.title)
        .join(QuizQuestion, Attempt.question_id == QuizQuestion.id)
        .outerjoin(Lesson, QuizQuestion.lesson_id == Lesson.id)
        .where(Attempt.user_id == user_id)
        .order_by(Attempt.created_at.desc())).all()
    return [{"at": a.created_at.isoformat(), "lesson_id": q.lesson_id, "lesson_title": title or q.lesson_id,
             "structure_id": q.structure_id, "difficulty": q.difficulty, "prompt": q.prompt,
             "answer": q.correct, "correct": bool(a.correct)} for a, q, title in rows]
