from dataclasses import dataclass
import imagehash
from PIL import Image
from sqlalchemy import select, func
from app.models.content import Page, Lesson
from app.core.config import settings
from app.recognition.embedder import open_image, embed_image, classify

@dataclass
class RecognitionResult:
    lesson_id: str | None
    confidence: float
    detected_labels: list[str]
    decision: str

def _phash(image: bytes | Image.Image) -> str | None:
    img = open_image(image) if isinstance(image, bytes) else image
    return str(imagehash.phash(img)) if img is not None else None

def _phash_similarity(a: str, b: str) -> float:
    ha, hb = imagehash.hex_to_hash(a), imagehash.hex_to_hash(b)
    return 1.0 - (ha-hb)/ len(ha.hash) ** 2

def _decide(ranked: list[tuple[str, float]]) -> RecognitionResult:
    if not ranked:
        return RecognitionResult(None, 0.0, [], "rescan")
    lesson_id, sim = ranked[0]
    margin = sim - ranked[1][1] if len(ranked) > 1 else sim
    if sim < settings.recognition_min_threshold:
        return RecognitionResult(None, sim, [], "rescan")
    sure = sim >= settings.recognition_auto_threshold and margin >= settings.recognition_margin
    return RecognitionResult(lesson_id, sim, [], "auto" if sure else "confirm")

_LEVEL = {"rescan": 0, "confirm": 1, "auto": 2}

def _decide_semantic(ranked: list[tuple[str, float]]) -> RecognitionResult:
    if not ranked or ranked[0][1] < settings.recognition_semantic_min:
        return RecognitionResult(None, ranked[0][1] if ranked else 0.0, [], "rescan")
    lesson_id, p = ranked[0]
    return RecognitionResult(lesson_id, p, [], "auto" if p >= settings.recognition_semantic_auto else "confirm")

def _combine(a: RecognitionResult, b: RecognitionResult) -> RecognitionResult:
    best = max(a, b, key=lambda r: _LEVEL[r.decision])
    if a.decision != "rescan" and b.decision != "rescan" and a.lesson_id != b.lesson_id:
        return RecognitionResult(best.lesson_id, best.confidence, [], "confirm")
    return best

def _subject(title: str) -> str:
    t = title.strip()
    return "the human " + (t[4:] if t.lower().startswith("the ") else t).lower()

def recognize(image_bytes: bytes, db) -> RecognitionResult:
    img = open_image(image_bytes)
    if img is None:
        return RecognitionResult(None, 0.0, [], "rescan")

    qhash = _phash(img)
    exact = max(((p.lesson_id, _phash_similarity(qhash, p.phash)) for p in db.execute(select(Page)).scalars()),
                key=lambda x: x[1], default=None)
    if exact and exact[1] >= settings.recognition_exact_threshold:
        return RecognitionResult(exact[0], exact[1], [], "auto")

    sim = (1 - Page.embedding.cosine_distance(embed_image(img))).label("sim")
    rows = db.execute(select(Page.lesson_id, func.max(sim).label("best"))
                      .group_by(Page.lesson_id).order_by(func.max(sim).desc())).all()
    by_example = _decide([(r.lesson_id, float(r.best)) for r in rows])
    subjects = {l.id: _subject(l.title) for l in db.execute(select(Lesson)).scalars()}
    return _combine(by_example, _decide_semantic(classify(img, subjects)))
