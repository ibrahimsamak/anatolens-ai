import json, struct
from pathlib import Path
import pytest
import yaml

CONTENT = Path(__file__).resolve().parents[2] / "content"
PACKS = sorted(p.parent for p in CONTENT.glob("*/structures.yaml"))

def _gltf(glb: Path) -> dict:
    data = glb.read_bytes()
    length = struct.unpack("<I", data[12:16])[0]
    return json.loads(data[20:20 + length])

@pytest.mark.parametrize("pack", PACKS, ids=[p.name for p in PACKS])
def test_each_structure_mesh_has_its_own_named_material(pack):
    [glb] = pack.glob("assets/*.glb")
    gltf = _gltf(glb)
    mats = [m.get("name") for m in gltf.get("materials", [])]
    node_mat = {}
    for n in gltf["nodes"]:
        if "mesh" in n:
            node_mat[n.get("name")] = {mats[p["material"]] for p in gltf["meshes"][n["mesh"]]["primitives"]
                                       if "material" in p}
    meshes = [s["mesh_name"] for s in yaml.safe_load((pack / "structures.yaml").read_text("utf-8")) if s.get("mesh_name")]
    for mesh in meshes:
        assert mesh in node_mat, f"{pack.name}: no GLB node named {mesh}"
        assert node_mat[mesh] & {f"{mesh}_mat", mesh}, f"{pack.name}: {mesh} materials {node_mat[mesh]} not named after it"
    owners = [m for mesh in meshes for m in node_mat[mesh]]
    assert len(owners) == len(set(owners)), f"{pack.name}: structures share a material, clicks can't tell them apart"
