import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from langgraph.types import Command
from app.api.deps import get_db, require_role, get_authoring_graph
from app.models.content import Lesson, Structure
from app.models.review import ReviewTask
from app.models.user import User
from app.services.review import advance, can_perform, EDITORS, REVIEWERS

router = APIRouter(prefix="/api/v1/admin")
STAFF = tuple(dict.fromkeys(EDITORS + REVIEWERS))

class LessonReq(BaseModel):
    id: str; title: str; system: str; model_url: str
    ios_model_url: str | None = None

class TransitionReq(BaseModel): action: str
class ReviewReq(BaseModel):
    decision: Literal["approve", "reject"]
    notes: str = ""

def _lesson(l: Lesson) -> dict:
    return {"id": l.id, "title": l.title, "system": l.system, "review_status": l.review_status}

def _task(t: ReviewTask) -> dict:
    return {"thread_id": t.thread_id, "lesson_id": t.lesson_id, "structure_id": t.structure_id, "status": t.status,
            "draft_text": t.draft_text, "created_by": t.created_by, "reviewer": t.reviewer, "notes": t.notes,
            "updated_at": t.updated_at.isoformat()}

def _email(db, user: dict) -> str:
    u = db.get(User, user["sub"])
    return u.email if u else user["sub"]

@router.get("/lessons")
def list_lessons(user=Depends(require_role(*STAFF)), db=Depends(get_db)):
    return [_lesson(l) for l in db.execute(select(Lesson).order_by(Lesson.title)).scalars()]

@router.post("/lessons", status_code=201)
def create_lesson(req: LessonReq, user=Depends(require_role(*EDITORS)), db=Depends(get_db)):
    if db.get(Lesson, req.id):
        raise HTTPException(409, "lesson already exists")
    lesson = Lesson(**req.model_dump(), review_status="DRAFT")
    db.add(lesson)
    db.commit()
    return _lesson(lesson)

@router.post("/lessons/{lesson_id}/transition")
def transition(lesson_id: str, req: TransitionReq, user=Depends(require_role(*STAFF)), db=Depends(get_db)):
    if not can_perform(user["role"], req.action):
        raise HTTPException(403, f"{user['role']} cannot {req.action}")
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(404, "unknown lesson")
    try:
        lesson.review_status = advance(lesson.review_status, req.action)
    except ValueError as e:
        raise HTTPException(409, str(e))
    db.commit()
    return _lesson(lesson)

@router.post("/lessons/{lesson_id}/author", status_code=201)
def author(lesson_id: str, structure_id: str, user=Depends(require_role(*EDITORS)), db=Depends(get_db),
           graph=Depends(get_authoring_graph)):
    s = db.get(Structure, structure_id)
    if not s or s.lesson_id != lesson_id:
        raise HTTPException(404, "unknown structure for this lesson")
    thread_id = f"{lesson_id}:{structure_id}:{uuid.uuid4().hex[:8]}"
    cfg = {"configurable": {"thread_id": thread_id}}
    out = graph.invoke({"lesson_id": lesson_id, "structure_id": structure_id, "structure_name": s.display_name_en}, cfg)
    task = ReviewTask(thread_id=thread_id, lesson_id=lesson_id, structure_id=structure_id, status=out["status"], draft_text=out.get("draft_text", ""), created_by=_email(db, user))
    db.add(task)
    db.commit()
    return _task(task) | {"interrupted": bool(out.get("__interrupt__"))}

@router.get("/reviews")
def list_reviews(status: str | None = "MEDICAL_REVIEW", user=Depends(require_role(*STAFF)), db=Depends(get_db)):
    q = select(ReviewTask).order_by(ReviewTask.updated_at.desc())
    if status:
        q = q.where(ReviewTask.status == status)
    return [_task(t) for t in db.execute(q).scalars()]

@router.post("/review/{thread_id}")
def review(thread_id: str, req: ReviewReq, user=Depends(require_role(*REVIEWERS)), db=Depends(get_db), graph=Depends(get_authoring_graph)):
    task = db.get(ReviewTask, thread_id)
    if not task:
        raise HTTPException(404, "unknown review")
    cfg = {"configurable": {"thread_id": thread_id}}
    if task.status != "MEDICAL_REVIEW" or not graph.get_state(cfg).interrupts:
        raise HTTPException(409, f"review is not awaiting a decision (status {task.status})")
    reviewer = _email(db, user)
    final = graph.invoke(Command(resume={"decision": req.decision, "reviewer": reviewer, "notes": req.notes}), cfg)
    task.status, task.reviewer, task.notes = final["status"], reviewer, req.notes or None
    db.commit()
    return _task(task) | {"chunk_id": final.get("chunk_id") or None}
