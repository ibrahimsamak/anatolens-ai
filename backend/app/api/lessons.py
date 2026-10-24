from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.api.deps import get_db
from app.models.content import Lesson, Structure
router = APIRouter(prefix="/api/v1")


@router.get("/lessons")
def list_lessons(db=Depends(get_db)):
    rows = db.execute(select(Lesson).order_by(Lesson.title)).scalars().all()
    return [{"id": l.id, "title": l.title, "system": l.system} for l in rows]

@router.get("/lessons/{lesson_id}")
def get_lesson(lesson_id: str, db=Depends(get_db)):
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(404)
    return {"id": lesson.id, "title": lesson.title, "model_url": lesson.model_url, "ios_model_url": lesson.ios_model_url}

@router.get("/lessons/{lesson_id}/structures")
def list_structures(lesson_id: str, db=Depends(get_db)):
    rows = db.execute(select(Structure).where(Structure.lesson_id == lesson_id)).scalars().all()
    return [{"id": s.id, "mesh_name": s.mesh_name, "name_en": s.display_name_en,
             "name_ar": s.display_name_ar} for s in rows if s.mesh_name]