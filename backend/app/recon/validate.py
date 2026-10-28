import numpy as np
import trimesh


def validate_mesh(glb_path):
    try:
        scene = trimesh.load(glb_path, force="scene")
    except Exception as e:
        return False, f"unreadable GLB: {e}"
    if not scene.geometry:
        return False, "mesh has 0 faces (degenerate reconstruction)"
    mesh = scene.to_geometry()
    if len(mesh.faces) == 0:
        return False, "mesh has 0 faces (degenerate reconstruction)"
    if not np.isfinite(mesh.vertices).all():
        return False, "mesh has non-finite vertices"
    if not mesh.is_watertight and len(mesh.faces) < 100:
        return False, "mesh too sparse / not usable"
    return True, "ok"
