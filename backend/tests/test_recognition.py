import pytest
from app.recognition.pipeline import recognize
from app.db.session import SessionLocal

@pytest.mark.integration
def test_known_spine_page_recognized(spine_page_image_bytes):
    r = recognize(spine_page_image_bytes, SessionLocal())
    assert r.lesson_id == "spine_001" and r.decision in {"auto", "confirm"}

@pytest.mark.integration
def test_random_noise_image_triggers_rescan(spine_page_image_bytes, noise_image_bytes):
    r = recognize(noise_image_bytes, SessionLocal())
    assert r.decision == "rescan" and r.lesson_id is None
