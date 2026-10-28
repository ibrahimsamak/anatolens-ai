import io
from pathlib import Path
from types import SimpleNamespace
import pytest
from PIL import Image
from pydantic import ValidationError
from app.cv import relations
from app.schemas.relations import DiagramRelations, Relation
from app.cv.proposals import save_proposals
from app.graph.anatomy_graph import build_graph
from app.models.graph_ops import EdgeProposal

SPINE_STRUCTURES = str(Path(__file__).resolve().parents[2] / "content" / "spine" / "structures.yaml")


class FakeDB:
    def __init__(self): self.rows, self.commits = {}, 0
    def merge(self, p): self.rows[p.id] = p
    def commit(self): self.commits += 1


def proposal(pid, s, pred, o):
    return EdgeProposal(id=pid, lesson_id="spine_001", subject_id=s, predicate=pred, object_id=o, confidence=0.6)


def fake_model(monkeypatch, *triples, sent=None):
    def invoke(msgs):
        if sent is not None:
            sent["content"] = msgs[0]["content"]
        return DiagramRelations(relations=[Relation(subject=s, predicate=p, object=o) for s, p, o in triples])
    structured = SimpleNamespace(invoke=invoke)
    monkeypatch.setattr(relations, "get_vision_model",
                        lambda: SimpleNamespace(with_structured_output=lambda schema: structured))


def test_extract_keeps_only_known_ids(monkeypatch):
    fake_model(monkeypatch,
               ("Lumbar", "connects_to", "Sacrum"),
               ("Lumbar", "connects_to", "Sacrum"),
               ("Flux capacitor", "part_of", "Spine"),
               ("Coccyx", "part_of", "Coccyx"))
    props = relations.extract_relations(b"not-an-image", "spine_001", SPINE_STRUCTURES)
    assert [(p.subject_id, p.predicate, p.object_id) for p in props] == \
           [("spine.lumbar_region", "connects_to", "spine.sacral_region")]
    assert props[0].status == "AI_GENERATED"


def test_prompt_lists_lesson_structures_and_ids_resolve(monkeypatch):
    sent = {}
    fake_model(monkeypatch, ("spine.coccygeal_region", "part_of", "spine.vertebral_column"), sent=sent)
    buf = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buf, format="JPEG")

    props = relations.extract_relations(buf.getvalue(), "spine_001", SPINE_STRUCTURES)
    text, image = sent["content"][0]["text"], sent["content"][1]["image_url"]["url"]
    assert "- spine.lumbar_region: " in text and "{structures}" not in text
    assert image.startswith("data:image/jpeg;base64,")
    assert [(p.subject_id, p.object_id) for p in props] == [("spine.coccygeal_region", "spine.vertebral_column")]


def test_extract_empty_reply(monkeypatch):
    fake_model(monkeypatch)
    assert relations.extract_relations(b"x", "spine_001", SPINE_STRUCTURES) == []


def test_schema_rejects_unknown_predicate():
    with pytest.raises(ValidationError):
        Relation(subject="a", predicate="eats", object="b")


def test_conflicts_flagged_not_applied_and_known_edges_skipped():
    g = build_graph(SPINE_STRUCTURES)
    db = FakeDB()
    n = save_proposals([
        proposal("wrong_parent", "spine.lumbar_region", "part_of", "spine.cervical_region"),
        proposal("reversed", "spine.vertebral_column", "part_of", "spine.lumbar_region"),
        proposal("new_ok", "spine.coccygeal_region", "connects_to", "spine.lumbar_region"),
        proposal("known", "spine.lumbar_region", "part_of", "spine.vertebral_column"),
    ], g, db)
    assert n == 3 and "known" not in db.rows
    assert db.rows["wrong_parent"].conflict and db.rows["reversed"].conflict
    assert db.rows["new_ok"].conflict is False
    assert all(p.status == "AI_GENERATED" for p in db.rows.values())
    assert "spine.cervical_region" not in g.objects("spine.lumbar_region", "part_of")


@pytest.mark.integration
def test_conflicting_edge_flagged_not_applied():
    from app.db.session import SessionLocal
    g = build_graph(SPINE_STRUCTURES)
    bad = proposal("p1", "spine.lumbar_region", "part_of", "spine.cervical_region")
    with SessionLocal() as db:
        n = save_proposals([bad], g, db)
    with SessionLocal() as db:
        saved = db.get(EdgeProposal, "p1")
        assert n == 1 and saved.conflict is True and saved.status == "AI_GENERATED"
        db.delete(saved)
        db.commit()
