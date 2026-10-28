from pathlib import Path
from types import SimpleNamespace
import pytest
import trimesh
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.api import deps
from app.core.security import create_token
from app.graph.anatomy_graph import build_graph
from app.models.content import Lesson, Structure
from app.models.graph_ops import EdgeProposal, MeshCandidate

SPINE = Path(__file__).resolve().parents[2] / "content" / "spine"


def bearer(role: str) -> dict:
    return {"Authorization": f"Bearer {create_token(f'test-{role.lower()}', role)}"}


class FakeDB:
    def __init__(self, rows, structures=()):
        self.rows, self.structures = {(type(r), r.id): r for r in rows}, list(structures)
    def get(self, model, key): return self.rows.get((model, key))
    def execute(self, _q): return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: self.structures))
    def commit(self): pass


@pytest.fixture
def client_with(monkeypatch):
    monkeypatch.setattr("app.api.admin.get_cache", lambda: None)
    def make(db, graph=None):
        app.dependency_overrides[deps.get_db] = lambda: db
        app.dependency_overrides[deps.get_anatomy_graph] = lambda: graph or build_graph(str(SPINE / "structures.yaml"))
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")
    yield make
    app.dependency_overrides.clear()


def edge(status="AI_GENERATED"):
    return EdgeProposal(id="e1", lesson_id="spine_001", subject_id="spine.coccygeal_region",
                        predicate="connects_to", object_id="spine.lumbar_region", status=status)


async def test_approve_proposal_writes_edge_into_graph(client_with):
    g, p = build_graph(str(SPINE / "structures.yaml")), edge()
    async with client_with(FakeDB([p]), g) as c:
        r = await c.post("/api/v1/admin/proposals/e1/approve", headers=bearer("MEDICAL_REVIEWER"))
        again = await c.post("/api/v1/admin/proposals/e1/reject", headers=bearer("MEDICAL_REVIEWER"))
    assert r.status_code == 200 and r.json()["status"] == "APPROVED"
    assert "spine.lumbar_region" in g.objects("spine.coccygeal_region", "connects_to")
    assert again.status_code == 409


async def test_reject_proposal_leaves_graph_and_editor_forbidden(client_with):
    g, p = build_graph(str(SPINE / "structures.yaml")), edge()
    async with client_with(FakeDB([p]), g) as c:
        forbidden = await c.post("/api/v1/admin/proposals/e1/approve", headers=bearer("CONTENT_EDITOR"))
        r = await c.post("/api/v1/admin/proposals/e1/reject", headers=bearer("SUPER_ADMIN"))
        unknown = await c.post("/api/v1/admin/proposals/nope/approve", headers=bearer("SUPER_ADMIN"))
    assert forbidden.status_code == 403 and r.json()["status"] == "DRAFT" and unknown.status_code == 404
    assert "spine.lumbar_region" not in g.objects("spine.coccygeal_region", "connects_to")


def test_approved_edges_reapplied_on_startup(monkeypatch):
    rows = [edge("APPROVED")]
    class Q:
        def filter_by(self, **kw): return self
        def all(self): return rows
    class S:
        def __init__(self, _engine): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def query(self, _m): return Q()
    monkeypatch.setattr("sqlalchemy.orm.Session", S)
    g = build_graph(str(SPINE / "structures.yaml"))
    assert deps.apply_approved_edges(g) == 1
    assert "spine.lumbar_region" in g.objects("spine.coccygeal_region", "connects_to")


async def test_mesh_missing_named_meshes_cannot_be_approved(client_with, tmp_path):
    glb = tmp_path / "box.glb"; trimesh.creation.box().export(glb)
    lesson = Lesson(id="spine_001", title="Spine", system="skeletal", model_url="/assets/spine.glb")
    m = MeshCandidate(id="m1", lesson_id="spine_001", glb_path=str(glb))
    lumbar = Structure(id="spine.lumbar_region", lesson_id="spine_001", mesh_name="Spine_Lumbar", display_name_en="Lumbar")
    async with client_with(FakeDB([lesson, m], [lumbar])) as c:
        r = await c.post("/api/v1/admin/meshes/m1/approve", headers=bearer("MEDICAL_REVIEWER"))
    assert r.status_code == 409 and "spine.lumbar_region" in str(r.json())
    assert m.status == "AI_GENERATED" and lesson.model_url == "/assets/spine.glb"


async def test_mesh_with_named_meshes_approved_and_rejected_draft_stays_out(client_with):
    lesson = Lesson(id="spine_001", title="Spine", system="skeletal", model_url="/assets/old.glb")
    good = MeshCandidate(id="m1", lesson_id="spine_001", glb_path=str(SPINE / "assets" / "spine.glb"))
    gated = MeshCandidate(id="m2", lesson_id="spine_001", glb_path="x.glb", status="DRAFT", reason="0 faces")
    lumbar = Structure(id="spine.lumbar_region", lesson_id="spine_001", mesh_name="Spine_Lumbar", display_name_en="Lumbar")
    async with client_with(FakeDB([lesson, good, gated], [lumbar])) as c:
        ok = await c.post("/api/v1/admin/meshes/m1/approve", headers=bearer("MEDICAL_REVIEWER"))
        blocked = await c.post("/api/v1/admin/meshes/m2/approve", headers=bearer("MEDICAL_REVIEWER"))
    assert ok.status_code == 200 and ok.json()["status"] == "APPROVED" and lesson.model_url == "/assets/spine.glb"
    assert blocked.status_code == 409


class AnalyzeDB(FakeDB):
    def merge(self, p): self.rows[(type(p), p.id)] = p
    def add(self, m): self.rows[(type(m), m.id)] = m


async def test_analyze_saves_proposals_and_skips_missing_models(client_with, monkeypatch):
    from app.cv import relations
    from app.schemas.relations import DiagramRelations, Relation
    reply = DiagramRelations(relations=[Relation(subject="Coccyx", predicate="connects_to", object="Lumbar"),
                                        Relation(subject="Sacrum", predicate="connects_to", object="Coccyx")])
    structured = SimpleNamespace(invoke=lambda msgs: reply)
    monkeypatch.setattr(relations, "get_vision_model", lambda: SimpleNamespace(with_structured_output=lambda schema: structured))
    def no_yolo(_image): raise ImportError("ultralytics")
    monkeypatch.setattr("app.api.admin.segment_regions", no_yolo)

    lesson = Lesson(id="spine_001", title="Spine", system="skeletal", model_url="/assets/spine.glb")
    db = AnalyzeDB([lesson])
    png = (SPINE / "assets" / "spine_preview.png").read_bytes()
    async with client_with(db) as c:
        r = await c.post("/api/v1/admin/lessons/spine_001/analyze", files={"file": ("d.png", png, "image/png")},
                         headers=bearer("CONTENT_EDITOR"))
        reviewer = await c.post("/api/v1/admin/lessons/spine_001/analyze", files={"file": ("d.png", png, "image/png")},
                                headers=bearer("MEDICAL_REVIEWER"))
        bad = await c.post("/api/v1/admin/lessons/spine_001/analyze", files={"file": ("d.png", b"nope", "image/png")},
                           headers=bearer("CONTENT_EDITOR"))
    body = r.json()
    assert r.status_code == 201 and len(body["proposals"]) == 1
    assert body["proposals"][0]["subject_id"] == "spine.coccygeal_region" and body["proposals"][0]["status"] == "AI_GENERATED"
    assert body["known"] == [{"subject_id": "spine.sacral_region", "predicate": "connects_to", "object_id": "spine.coccygeal_region"}]
    assert any("ultralytics" in n for n in body["notes"]) and body["mesh"] is None
    assert reviewer.status_code == 403 and bad.status_code == 400
