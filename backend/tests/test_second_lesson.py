from pathlib import Path
import pytest
import yaml
from httpx import AsyncClient, ASGITransport
from app.api.deps import get_anatomy_graph
from app.recognition.ontology import OntologyResolver

CONTENT = Path(__file__).resolve().parents[2] / "content"
HEART = yaml.safe_load((CONTENT / "heart" / "structures.yaml").read_text("utf-8"))


def test_heart_is_its_own_pack_with_no_code():
    lesson = yaml.safe_load((CONTENT / "heart" / "lesson.yaml").read_text("utf-8"))
    assert lesson["id"] == "heart_001" and lesson["review_status"] == "APPROVED"
    assert all(s["id"].startswith("heart.") for s in HEART)

def test_shared_graph_knows_heart_relations_without_mixing_lessons():
    n = get_anatomy_graph().neighbors("heart.left_ventricle", hops=1)
    assert n and all(sid.startswith("heart.") for sid in n)
    assert all(sid.startswith("spine.") for sid in get_anatomy_graph().neighbors("spine.lumbar_region", hops=1))

def test_heart_mesh_names_do_not_follow_the_spine_convention():
    # ids drive everything; the mesh names are whatever the heart GLB uses
    assert {s["mesh_name"] for s in HEART if s.get("mesh_name")} >= {"Heart_LeftVentricle", "Heart_MitralValve"}

def test_heart_labels_resolve():
    res = OntologyResolver.from_yaml(CONTENT / "heart" / "structures.yaml")
    assert res.resolve_fuzzy("Left Ventricle") == "heart.left_ventricle"


@pytest.mark.integration
async def test_heart_lesson_explains_left_ventricle():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/v1/structures/heart.left_ventricle/explain",
                         json={"question": "what does it do?", "locale": "en"})
    body = r.json()
    assert body["grounded"] and "ventricle" in body["text"].lower()

@pytest.mark.integration
async def test_heart_structures_endpoint_lists_clickable_parts():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/v1/lessons/heart_001/structures")
    meshes = {s["mesh_name"] for s in r.json()}
    assert "Heart_LeftVentricle" in meshes and None not in meshes
