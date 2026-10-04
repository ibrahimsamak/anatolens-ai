import sys, json, numpy as np, trimesh
from trimesh.visual.material import PBRMaterial
OBJ, OUT = sys.argv[1], sys.argv[2]
FJ = lambda *a: [f"FJ{n}" for n in a]

BONE, DISC = [227, 218, 201], [120, 170, 210]
SPINE = {
    "Spine_Cervical": (FJ(3176, 3177, 3161, 3164, 3167, 3170, 3172), [235, 214, 170]),
    "Spine_Thoracic": (FJ(3158, 3160, 3163, 3166, 3169, 3171, 3173, 3174, 3175, 3154, 3155, 3156), [226, 200, 160]),
    "Spine_Lumbar":   (FJ(3157, 3159, 3162, 3165, 3168), [214, 186, 146]),
    "Spine_Sacral":   (FJ(3393), [200, 172, 136]),
    "Spine_IntervertebralDiscs": (FJ(*range(3202, 3225)), DISC),
}
HEART = {
    "Heart_RightAtrium":    (FJ(2424, 2439), [70, 110, 190]),
    "Heart_RightVentricle": (FJ(2423, 2419, 2430, 2437), [90, 130, 210]),
    "Heart_LeftAtrium":     (FJ(2425, 2438), [200, 80, 80]),
    "Heart_LeftVentricle":  (FJ(2422, 2418, 2429, 2432), [180, 50, 55]),
    "Heart_TricuspidValve": (FJ(2421, 2433, 2436), [240, 230, 200]),
    "Heart_MitralValve":    (FJ(2420), [240, 230, 200]),
    "Heart_PulmonaryValve": (FJ(2417, 2427, 2434), [240, 230, 200]),
    "Heart_AorticValve":    (FJ(2426, 2431, 2435), [240, 230, 200]),
    "Heart_Aorta":          (FJ(3413, 3411), [205, 40, 45]),
    "Heart_PulmonaryTrunk": (FJ(2966), [80, 100, 200]),
    "Heart_SuperiorVenaCava": (FJ(3645), [60, 80, 170]),
    "Heart_InferiorVenaCava": (FJ(3441), [60, 80, 170]),
    "Heart_CoronaryArteries": (FJ(*range(2631, 2655), 2667, 2668, *range(2670, 2678), *range(2692, 2701), *range(2714, 2724), 2737), [230, 60, 50]),
    "Heart_CardiacVeins":   (FJ(2655, 2656, 2724, 2727, 2728, 2729, 2731), [70, 90, 180]),
}
CLIP_Z_MIN = {"Heart_InferiorVenaCava": 1160.0}
R = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]], float)
S = np.diag([0.001, 0.001, 0.001, 1.0])

def build(name, spec):
    import os
    meshes = {}
    for node, (els, rgb) in spec.items():
        parts = [trimesh.load(f"{OBJ}/{e}.obj", force="mesh") for e in els if os.path.exists(f"{OBJ}/{e}.obj")]
        missing = [e for e in els if not os.path.exists(f"{OBJ}/{e}.obj")]
        if missing: print(f"  {node}: skipped missing {missing}")
        m = trimesh.util.concatenate(parts)
        if node in CLIP_Z_MIN:
            m = m.slice_plane([0, 0, CLIP_Z_MIN[node]], [0, 0, 1], cap=True)
        m.apply_transform(S @ R)
        m.merge_vertices(); m.update_faces(m.nondegenerate_faces(height=1e-9))
        m.remove_unreferenced_vertices(); m.fix_normals()
        vn = m.vertex_normals.copy(); bad = np.linalg.norm(vn, axis=1) < 0.5
        vn[bad] = [0, 1, 0]; m.vertex_normals = vn / np.linalg.norm(vn, axis=1)[:, None]
        m.visual = trimesh.visual.TextureVisuals(material=PBRMaterial(
            name=f"{node}_mat", baseColorFactor=[*[c / 255 for c in rgb], 1.0],
            metallicFactor=0.0, roughnessFactor=0.65, doubleSided=True))
        meshes[node] = m
    allb = np.vstack([m.bounds for m in meshes.values()])
    lo, hi = allb.min(0), allb.max(0)
    shift = np.array([-(lo[0] + hi[0]) / 2, -lo[1], -(lo[2] + hi[2]) / 2])
    scene, hotspots = trimesh.Scene(), {}
    for node, m in meshes.items():
        m.apply_translation(shift)
        scene.add_geometry(m, node_name=node, geom_name=node)
        v, (b0, b1) = m.vertices, m.bounds
        cy, h = (b0[1] + b1[1]) / 2, b1[1] - b0[1]
        band = np.where(np.abs(v[:, 1] - cy) <= max(h * 0.15, 0.003))[0]
        i = band[np.argmax(v[band, 2])]
        hotspots[node] = {"position": [round(float(x), 4) for x in v[i]],
                          "normal": [round(float(x), 4) for x in m.vertex_normals[i]],
                          "triangles": int(len(m.faces))}
    path = f"{OUT}/{name}.glb"
    scene.export(path)
    size = (hi - lo) * 1
    print(f"{path}: {len(meshes)} nodes, size(m)={np.round(hi - lo, 3).tolist()}")
    json.dump(hotspots, open(f"{OUT}/{name}.hotspots.json", "w"), indent=1)

build("spine", SPINE)
build("heart", HEART)
