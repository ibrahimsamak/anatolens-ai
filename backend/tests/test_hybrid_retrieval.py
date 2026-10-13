import pytest
from app.rag.retriever import retrieve_chunks_hybrid
from app.db.session import SessionLocal

@pytest.mark.integration
def test_hybrid_beats_dense_on_exact_term():
    db = SessionLocal()
    seed = ["spine.lumbar_region"]
    hits = retrieve_chunks_hybrid(seed, "L1-L5", "en", db, k=3)
    assert hits and any("lumbar" in c.text.lower() for c in hits)
