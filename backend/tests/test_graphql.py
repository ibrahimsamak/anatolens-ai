import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.api.deps import get_db
from app.models.base import Base
from app.models.content import Lesson, Structure, KnowledgeChunk

LESSON_Q = '{ lesson(id:"spine_001"){ title structures { id nameEn } } }'

async def _post(query: str) -> dict:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/graphql", json={"query": query})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "errors" not in body, body["errors"]
    return body["data"]

@pytest.mark.integration
async def test_graphql_lesson_with_structures():
    data = (await _post(LESSON_Q))["lesson"]
    assert data["title"] and any(s["id"] == "spine.lumbar_region" for s in data["structures"])


@pytest.fixture
def sqlite_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        db.add(Lesson(id="spine_001", title="Vertebral Column", system="skeletal", model_url="/assets/spine.glb"))
        db.add_all([
            Structure(id="spine.lumbar_region", lesson_id="spine_001", mesh_name="Spine_Lumbar",
                      display_name_en="Lumbar region (L1-L5)", display_name_ar="المنطقة القطنية"),
            Structure(id="spine.coccygeal_region", lesson_id="spine_001", mesh_name=None, display_name_en="Coccyx"),
        ])
        db.add_all([
            KnowledgeChunk(id="k1", lesson_id="spine_001", structure_id="spine.lumbar_region", locale="en",
                           text="Lumbar vertebrae bear weight.", review_status="APPROVED", source="Gray's",
                           embedding=[0.0] * 1536),
            KnowledgeChunk(id="k2", lesson_id="spine_001", structure_id="spine.lumbar_region", locale="en",
                           text="Unreviewed draft.", review_status="DRAFT", embedding=[0.0] * 1536),
            KnowledgeChunk(id="k3", lesson_id="spine_001", structure_id="spine.lumbar_region", locale="ar",
                           text="الفقرات القطنية تحمل الوزن.", review_status="APPROVED", embedding=[0.0] * 1536),
        ])
        db.commit()

    def override():
        with Session() as db:
            yield db
    app.dependency_overrides[get_db] = override
    yield
    app.dependency_overrides.pop(get_db, None)

async def test_lesson_resolves_nested_structures(sqlite_db):
    data = (await _post(LESSON_Q))["lesson"]
    assert data["title"] == "Vertebral Column"
    assert {s["id"] for s in data["structures"]} == {"spine.lumbar_region", "spine.coccygeal_region"}

async def test_knowledge_is_approved_only_and_per_locale(sqlite_db):
    data = await _post('{ en: knowledge(structureId:"spine.lumbar_region"){ text source }'
                       '  ar: knowledge(structureId:"spine.lumbar_region", locale:"ar"){ text } }')
    assert [k["text"] for k in data["en"]] == ["Lumbar vertebrae bear weight."]
    assert len(data["ar"]) == 1

async def test_unknown_lesson_is_null(sqlite_db):
    assert (await _post('{ lesson(id:"nope"){ title } }'))["lesson"] is None

async def test_rest_structures_endpoint_skips_missing_mesh(sqlite_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/v1/lessons/spine_001/structures")
    assert r.status_code == 200
    assert [s["id"] for s in r.json()] == ["spine.lumbar_region"]
