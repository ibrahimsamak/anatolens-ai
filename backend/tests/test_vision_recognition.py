import pytest
from app.recognition.vision import embed_image, search_pages_by_embedding, ocr_labels
from app.db.session import SessionLocal


@pytest.mark.integration
def test_embedding_search_finds_spine(spine_page_image_bytes):
    vec = embed_image(spine_page_image_bytes)
    assert len(vec) == 512
    with SessionLocal() as db:
        hits = search_pages_by_embedding(vec, db, k=1)
    assert hits and hits[0][0].lesson_id == "spine_001"
    assert hits[0][1] > 0.99   


def test_unreadable_image_cannot_be_embedded():
    with pytest.raises(ValueError):
        embed_image(b"not an image")


def test_ocr_on_unreadable_image_returns_no_labels():
    assert ocr_labels(b"not an image") == []
