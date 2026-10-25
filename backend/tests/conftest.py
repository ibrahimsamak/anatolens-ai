import io
import random
from pathlib import Path
import pytest
from PIL import Image
from app.content.ingest import _load
from app.db.session import SessionLocal
from app.models.content import Lesson, Page
from app.recognition.pipeline import _phash
from app.recognition.embedder import open_image, embed_image
from app.schemas.content import LessonSpec

CONTENT = Path(__file__).resolve().parents[2] / "content"
SPINE_PAGE_ID = "spine_page_fixture"


@pytest.fixture
def spine_page_image_bytes():
    image_bytes = (CONTENT / "spine" / "assets" / "spine_preview.png").read_bytes()
    with SessionLocal() as db:
        lesson = LessonSpec(**_load(CONTENT / "spine" / "lesson.yaml"))
        db.merge(Lesson(**lesson.model_dump()))
        img = open_image(image_bytes)
        db.merge(Page(id=SPINE_PAGE_ID, lesson_id=lesson.id,
                      phash=_phash(img), embedding=embed_image(img)))
        db.commit()
    yield image_bytes
    with SessionLocal() as db:
        db.query(Page).filter_by(id=SPINE_PAGE_ID).delete()
        db.commit()


@pytest.fixture
def noise_image_bytes():
    rng = random.Random(42)
    img = Image.frombytes("L", (256, 256), bytes(rng.getrandbits(8) for _ in range(256 * 256)))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
