import strawberry
from fastapi import Depends
from sqlalchemy import select
from app.api.deps import get_db
from app.models.content import Lesson as LessonM, Structure as StructM, KnowledgeChunk

async def get_context(db=Depends(get_db)) -> dict:
    return {"db": db}

def _knowledge(db, structure_id: str, locale: str) -> list["Knowledge"]:
    rows = db.execute(select(KnowledgeChunk).where(
        KnowledgeChunk.structure_id == structure_id,
        KnowledgeChunk.locale == locale,
        KnowledgeChunk.review_status == "APPROVED")).scalars().all()
    return [Knowledge(text=r.text, source=r.source, source_version=r.source_version) for r in rows]

def _structures(db, lesson_id: str) -> list["Structure"]:
    rows = db.execute(select(StructM).where(StructM.lesson_id == lesson_id)).scalars().all()
    return [Structure(id=s.id, name_en=s.display_name_en, name_ar=s.display_name_ar, mesh_name=s.mesh_name)
            for s in rows]

@strawberry.type
class Knowledge:
    text: str
    source: str
    source_version: str

@strawberry.type
class Structure:
    id: str
    name_en: str
    name_ar: str | None
    mesh_name: str | None

    @strawberry.field
    def knowledge(self, info: strawberry.Info, locale: str = "en") -> list[Knowledge]:
        return _knowledge(info.context["db"], self.id, locale)

@strawberry.type
class Lesson:
    id: str
    title: str
    system: str
    model_url: str
    ios_model_url: str | None

    @strawberry.field
    def structures(self, info: strawberry.Info) -> list[Structure]:
        return _structures(info.context["db"], self.id)

def _lesson(l: LessonM) -> Lesson:
    return Lesson(id=l.id, title=l.title, system=l.system, model_url=l.model_url, ios_model_url=l.ios_model_url)

@strawberry.type
class Query:
    @strawberry.field
    def lesson(self, info: strawberry.Info, id: str) -> Lesson | None:
        l = info.context["db"].get(LessonM, id)
        return _lesson(l) if l else None

    @strawberry.field
    def lessons(self, info: strawberry.Info) -> list[Lesson]:
        return [_lesson(l) for l in info.context["db"].execute(select(LessonM)).scalars().all()]

    @strawberry.field
    def structures(self, info: strawberry.Info, lesson_id: str) -> list[Structure]:
        return _structures(info.context["db"], lesson_id)

    @strawberry.field
    def knowledge(self, info: strawberry.Info, structure_id: str, locale: str = "en") -> list[Knowledge]:
        return _knowledge(info.context["db"], structure_id, locale)

schema = strawberry.Schema(Query)
