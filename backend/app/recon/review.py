import trimesh


def can_approve_mesh(glb_path, required_structure_ids, mesh_names=None):
    mesh_names = mesh_names or {}
    try:
        scene = trimesh.load(glb_path, force="scene")
        names = [n.lower() for n in [*scene.geometry, *scene.graph.nodes_geometry]]
    except Exception:
        names = []
    missing = []
    for sid in required_structure_ids:
        wanted = (mesh_names.get(sid) or sid.split(".")[-1]).lower()
        if not any(wanted in n for n in names):
            missing.append(sid)
    return not missing, missing
