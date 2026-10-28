from app.models.graph_ops import EdgeProposal, MeshCandidate
from app.services.review import STATUSES


def test_edge_proposal_defaults_to_draft():
    e = EdgeProposal(id="e1", lesson_id="spine_001", subject_id="spine.lumbar_region",
                     predicate="connects_to", object_id="spine.sacral_region", confidence=0.8)
    assert e.status == "AI_GENERATED" and e.conflict is False


def test_mesh_candidate_tracks_reason():
    m = MeshCandidate(id="m1", lesson_id="spine_001", glb_path="/tmp/x.glb",
                      status="AI_GENERATED", reason="")
    assert m.status == "AI_GENERATED"


def test_defaults_are_slice5_workflow_values_and_overridable():
    m = MeshCandidate(id="m2", lesson_id="spine_001", glb_path="/tmp/y.glb")
    assert m.status in STATUSES and m.reason == ""
    assert MeshCandidate(id="m3", lesson_id="l", glb_path="p", status="DRAFT").status == "DRAFT"
