from fastapi import APIRouter, Depends, UploadFile, File
from app.api.deps import get_db
from app.recognition.pipeline import recognize
router = APIRouter(prefix="/api/v1")


@router.post("/recognition/page")
async def recognition_page(file: UploadFile=File(...), db=Depends(get_db)):
    r = recognize(await file.read(), db)
    return {"lesson_id": r.lesson_id, "confidence": r.confidence, "decision": r.decision}

