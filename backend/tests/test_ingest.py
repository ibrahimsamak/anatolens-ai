import pytest
from pathlib import Path
from app.content.ingest import ingest_pack
from app.db.session import SessionLocal
from app.models.content import Lesson, Structure, KnowledgeChunk

SPINE_PACK = Path(__file__).resolve().parents[2] / "content" / "spine"


@pytest.mark.integration
def test_ingest_spine_pack():
    db = SessionLocal()
    report = ingest_pack(SPINE_PACK, db)
    assert db.get(Lesson, "spine_001").review_status == "APPROVED"
    assert db.get(Structure, "spine.lumbar_region").mesh_name == "Spine_Lumbar"
    chunks = db.query(KnowledgeChunk).filter_by(structure_id="spine.lumbar_region").all()
    assert chunks and all(len(c.embedding) == 1536 for c in chunks)

