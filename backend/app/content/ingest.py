import uuid, yaml
from pathlib import Path
from dataclasses import dataclass
from app.schemas.content import LessonSpec, StructureSpec, KnowledgeSpec
from app.models.content import Lesson, Structure, KnowledgeChunk, Page
from app.llm.factory import get_embeddings
from app.recognition.pipeline import _phash
from app.rag.graphrag import get_cache

@dataclass
class IngestReport:
    lesson_id: str
    structures: int
    chunks: int
    
def _load(p: Path): 
    return yaml.safe_load(p.read_text(encoding="utf-8"))

def ingest_pack(path: str, db) -> IngestReport:
    root = Path(path)
    lesson = LessonSpec(**_load(root / "lesson.yaml"))
    db.merge(Lesson(**lesson.model_dump()))
    
    structs = [StructureSpec(**s) for s in _load(root/ "structures.yaml")]
    for s in structs:
        db.merge(Structure(id=s.id, lesson_id=lesson.id, mesh_name=s.mesh_name, display_name_en=s.display_name_en, display_name_ar=s.display_name_ar))
    
    for preview in sorted((root / "assets").glob("*_preview.png")):
        db.merge(Page(id=f"{lesson.id}:{preview.stem}", lesson_id=lesson.id,
                      phash=_phash(preview.read_bytes()), embedding=[0.0] * 512))
    db.flush()

    emb = get_embeddings()
    chunks = [KnowledgeSpec(**k) for k in _load(root/"knowledge.en.yaml")]
    vectors = emb.embed_documents([c.text for c in chunks])
    db.query(KnowledgeChunk).filter_by(lesson_id=lesson.id, locale="en").delete()
    for c, v in zip(chunks, vectors):
        db.merge(KnowledgeChunk(
            id= str(uuid.uuid4()),
            lesson_id= lesson.id,
            structure_id = c.structure_id,
            locale= "en",
            text= c.text,
            review_status= c.review_status,
            source= c.source,
            source_version= c.source_version,
            reviewer= c.reviewer,
            embedding=v
        ))
        
    db.commit()
    if cache := get_cache(): 
        cache.clear([s.id for s in structs])
    return IngestReport(lesson.id, len(structs), len(chunks))