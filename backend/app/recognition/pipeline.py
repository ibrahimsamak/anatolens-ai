import io 
from dataclasses import dataclass
import imagehash
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from app.models.content import Page
from app.core.config import settings

@dataclass
class RecognitionResult:
    lesson_id: str | None
    confidence: float
    detected_labels: list[str]
    decision: str
    
def _phash(image_bytes: bytes) -> str | None:
    try:
        return str(imagehash.phash(Image.open(io.BytesIO(image_bytes))))
    except (UnidentifiedImageError, OSError):
        return None

def _phash_similarity(a: str, b: str) -> float:
    ha, hb = imagehash.hex_to_hash(a), imagehash.hex_to_hash(b)
    return 1.0 - (ha-hb)/ len(ha.hash) ** 2

def recognize(image_bytes: bytes, db) -> RecognitionResult:
    qhash = _phash(image_bytes)
    if qhash is None:
        return RecognitionResult(None, 0.0, [], "rescan")
    pages = db.execute(select(Page)).scalars().all()
    best, best_sim = None, 0.0
    for p in pages:
        sim = _phash_similarity(qhash, p.phash)
        if sim > best_sim:
            best = p
            best_sim = sim
    if not best or best_sim< settings.recognition_min_threshold:
        return RecognitionResult(None, best_sim, [], "rescan")
    decision = "auto"  if best_sim >= settings.recognition_auto_threshold  else "confirm"
    return RecognitionResult(best.lesson_id, best_sim, [], decision)