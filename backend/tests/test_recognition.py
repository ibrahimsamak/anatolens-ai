import io
import pytest
from PIL import Image, ImageFilter
from app.recognition.pipeline import recognize, _decide
from app.db.session import SessionLocal


def _photo_of(image_bytes: bytes) -> bytes:
    """The page as a phone sees it: on a desk, tilted, a bit blurry, JPEG."""
    page = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    desk = Image.new("RGB", (int(page.width * 1.5), int(page.height * 1.5)), (150, 120, 90))
    desk.paste(page.rotate(8, expand=True, fillcolor=(150, 120, 90)), (page.width // 6, page.height // 8))
    out = io.BytesIO()
    desk.filter(ImageFilter.GaussianBlur(1.5)).save(out, "JPEG", quality=70)
    return out.getvalue()


@pytest.mark.integration
def test_known_spine_page_recognized(spine_page_image_bytes):
    r = recognize(spine_page_image_bytes, SessionLocal())
    assert r.lesson_id == "spine_001" and r.decision == "auto"

@pytest.mark.integration
def test_photo_of_spine_page_recognized(spine_page_image_bytes):
    r = recognize(_photo_of(spine_page_image_bytes), SessionLocal())
    assert r.lesson_id == "spine_001" and r.decision in {"auto", "confirm"}

@pytest.mark.integration
def test_random_noise_image_triggers_rescan(spine_page_image_bytes, noise_image_bytes):
    r = recognize(noise_image_bytes, SessionLocal())
    assert r.decision == "rescan" and r.lesson_id is None

def test_unreadable_image_triggers_rescan():
    assert recognize(b"not an image", db=None).decision == "rescan"


@pytest.mark.parametrize("ranked, expected", [
    ([], (None, "rescan")),
    ([("spine_001", 0.20), ("heart_001", 0.10)], (None, "rescan")),
    ([("spine_001", 0.60), ("heart_001", 0.30)], ("spine_001", "auto")),
    ([("spine_001", 0.40), ("heart_001", 0.20)], ("spine_001", "confirm")),   # similar, but not sure enough
    ([("spine_001", 0.60), ("heart_001", 0.57)], ("spine_001", "confirm")),   # too close to call
    ([("spine_001", 0.60)], ("spine_001", "auto")),
])
def test_decision_thresholds(ranked, expected, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "recognition_min_threshold", 0.35)
    monkeypatch.setattr(settings, "recognition_auto_threshold", 0.45)
    monkeypatch.setattr(settings, "recognition_margin", 0.08)
    r = _decide(ranked)
    assert (r.lesson_id, r.decision) == expected


@pytest.mark.parametrize("ranked, expected", [
    ([], (None, "rescan")),
    ([("heart_001", 0.30), ("spine_001", 0.20)], (None, "rescan")),
    ([("heart_001", 0.70), ("spine_001", 0.10)], ("heart_001", "confirm")),
    ([("heart_001", 0.95), ("spine_001", 0.01)], ("heart_001", "auto")),
])
def test_semantic_decision(ranked, expected, monkeypatch):
    from app.core.config import settings
    from app.recognition.pipeline import _decide_semantic
    monkeypatch.setattr(settings, "recognition_semantic_min", 0.5)
    monkeypatch.setattr(settings, "recognition_semantic_auto", 0.85)
    r = _decide_semantic(ranked)
    assert (r.lesson_id, r.decision) == expected


def test_combine_prefers_the_surer_signal_and_flags_disagreement():
    from app.recognition.pipeline import RecognitionResult as R, _combine
    rescan, heart_auto = R(None, 0.3, [], "rescan"), R("heart_001", 0.98, [], "auto")
    assert _combine(rescan, heart_auto) == heart_auto
    assert _combine(R("heart_001", 0.4, [], "confirm"), heart_auto) == heart_auto
    disagree = _combine(R("spine_001", 0.6, [], "auto"), heart_auto)
    assert disagree.decision == "confirm"


def test_lesson_title_becomes_subject():
    from app.recognition.pipeline import _subject
    assert _subject("The Heart") == "the human heart"
    assert _subject("Vertebral Column") == "the human vertebral column"
