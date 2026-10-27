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
STAFF = ("CONTENT_EDITOR", "MEDICAL_REVIEWER", "SUPER_ADMIN")


class LessonReq(BaseModel):
    id: str
    title: str
    system: str
    model_url: str
    ios_model_url: str | None = None

class TransitionReq(BaseModel): action: str

class ReviewReq(BaseModel):
    decision: Literal["approve", "reject"]
    notes: str = ""


def lesson_info(l: Lesson):
    return {"id": l.id, "title": l.title, "system": l.system, "review_status": l.review_status}


def task_info(t: ReviewTask):
    return {
        "thread_id": t.thread_id,
        "lesson_id": t.lesson_id,
        "structure_id": t.structure_id,
        "status": t.status,
        "draft_text": t.draft_text,
        "created_by": t.created_by,
        "reviewer": t.reviewer,
        "notes": t.notes,
        "updated_at": t.updated_at.isoformat(),
    }


def email_of(db, user):
    u = db.get(User, user["sub"])
    return u.email if u else user["sub"]


@router.get("/lessons", dependencies=[Depends(require_role(*STAFF))])
def list_lessons(db=Depends(get_db)):
    lessons = db.execute(select(Lesson).order_by(Lesson.title)).scalars()
    return [lesson_info(l) for l in lessons]


@router.post("/lessons", status_code=201, dependencies=[Depends(require_role(*EDITORS))])
def create_lesson(req: LessonReq, db=Depends(get_db)):
    if db.get(Lesson, req.id):
        raise HTTPException(409, "lesson already exists")
    lesson = Lesson(**req.model_dump(), review_status="DRAFT")
    db.add(lesson)
    db.commit()
    return lesson_info(lesson)


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
    return lesson_info(lesson)


@router.post("/lessons/{lesson_id}/author", status_code=201)
def author(lesson_id: str, structure_id: str, user=Depends(require_role(*EDITORS)),
           db=Depends(get_db), graph=Depends(get_authoring_graph)):
    structure = db.get(Structure, structure_id)
    if not structure or structure.lesson_id != lesson_id:
        raise HTTPException(404, "unknown structure for this lesson")

    thread_id = f"{lesson_id}:{structure_id}:{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    out = graph.invoke({"lesson_id": lesson_id, "structure_id": structure_id,
                        "structure_name": structure.display_name_en}, config)

    task = ReviewTask(thread_id=thread_id, lesson_id=lesson_id, structure_id=structure_id,
                      status=out["status"], draft_text=out.get("draft_text", ""),
                      created_by=email_of(db, user))
    db.add(task)
    db.commit()

    result = task_info(task)
    result["interrupted"] = "__interrupt__" in out
    return result


@router.get("/reviews", dependencies=[Depends(require_role(*STAFF))])
def list_reviews(status: str = "MEDICAL_REVIEW", db=Depends(get_db)):
    query = select(ReviewTask).order_by(ReviewTask.updated_at.desc())
    if status:
        query = query.where(ReviewTask.status == status)
    return [task_info(t) for t in db.execute(query).scalars()]


@router.post("/review/{thread_id}")
def review(thread_id: str, req: ReviewReq, user=Depends(require_role(*REVIEWERS)),
           db=Depends(get_db), graph=Depends(get_authoring_graph)):
    task = db.get(ReviewTask, thread_id)
    if not task:
        raise HTTPException(404, "unknown review")

    config = {"configurable": {"thread_id": thread_id}}
    if task.status != "MEDICAL_REVIEW" or not graph.get_state(config).interrupts:
        raise HTTPException(409, f"review is not awaiting a decision (status {task.status})")

    reviewer = email_of(db, user)
    answer = {"decision": req.decision, "reviewer": reviewer, "notes": req.notes}
    final = graph.invoke(Command(resume=answer), config)

    task.status = final["status"]
    task.reviewer = reviewer
    task.notes = req.notes or None
    db.commit()

    result = task_info(task)
    result["chunk_id"] = final.get("chunk_id") or None
    return result
