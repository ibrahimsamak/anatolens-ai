from pathlib import Path
import trimesh, yaml
from app.recon.review import can_approve_mesh

SPINE = Path(__file__).resolve().parents[2] / "content" / "spine"


def test_missing_named_mesh_blocks_approval(tmp_path):
    p = tmp_path / "unnamed.glb"; trimesh.creation.box().export(p)
    ok, missing = can_approve_mesh(str(p), ["spine.lumbar_region"])
    assert not ok and "spine.lumbar_region" in missing


def test_real_spine_glb_passes_with_yaml_mesh_names():
    structures = [s for s in yaml.safe_load((SPINE / "structures.yaml").read_text("utf-8")) if s.get("mesh_name")]
    ok, missing = can_approve_mesh(str(SPINE / "assets" / "spine.glb"), [s["id"] for s in structures],
                                   {s["id"]: s["mesh_name"] for s in structures})
    assert ok, missing


def test_one_missing_mesh_is_reported(tmp_path):
    scene = trimesh.Scene()
    scene.add_geometry(trimesh.creation.box(), geom_name="Spine_Lumbar", node_name="Spine_Lumbar")
    p = tmp_path / "partial.glb"; scene.export(p)
    ok, missing = can_approve_mesh(str(p), ["spine.lumbar_region", "spine.sacral_region"],
                                   {"spine.lumbar_region": "Spine_Lumbar", "spine.sacral_region": "Spine_Sacral"})
    assert not ok and missing == ["spine.sacral_region"]
