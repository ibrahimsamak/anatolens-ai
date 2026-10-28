import trimesh, numpy as np
from app.recon.validate import validate_mesh


def test_empty_mesh_rejected(tmp_path):
    p = tmp_path / "empty.glb"
    trimesh.Trimesh(vertices=np.zeros((0, 3)), faces=np.zeros((0, 3))).export(p)
    ok, reason = validate_mesh(str(p))
    assert not ok and "face" in reason.lower()


def test_valid_box_accepted(tmp_path):
    p = tmp_path / "box.glb"; trimesh.creation.box().export(p)
    ok, reason = validate_mesh(str(p))
    assert ok


def test_sparse_open_mesh_rejected(tmp_path):
    p = tmp_path / "tri.glb"
    trimesh.Trimesh(vertices=[[0, 0, 0], [1, 0, 0], [0, 1, 0]], faces=[[0, 1, 2]]).export(p)
    ok, reason = validate_mesh(str(p))
    assert not ok and "sparse" in reason


def test_unreadable_file_rejected_not_crash(tmp_path):
    p = tmp_path / "junk.glb"; p.write_bytes(b"not a glb")
    ok, reason = validate_mesh(str(p))
    assert not ok and reason
