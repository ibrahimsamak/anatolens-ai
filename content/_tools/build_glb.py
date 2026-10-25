import sys, json, numpy as np, trimesh
from trimesh.visual.material import PBRMaterial
from anchors import anchor, model_frame
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
DIGESTIVE = {
    "Digestive_Esophagus":       (FJ(2563), [214, 120, 120]),
    "Digestive_Stomach":         (FJ(2564), [224, 128, 118]),
    "Digestive_Duodenum":        (FJ(2573), [232, 168, 120]),
    "Digestive_Jejunum":         (FJ(*range(2606, 2629)), [236, 150, 138]),
    "Digestive_Ileum":           (FJ(*range(2574, 2599), *range(2600, 2606)), [226, 140, 128]),
    "Digestive_Cecum":           (FJ(2599), [192, 142, 100]),
    "Digestive_Appendix":        (FJ(2565), [205, 152, 110]),
    "Digestive_AscendingColon":  (FJ(2566), [200, 152, 104]),
    "Digestive_TransverseColon": (FJ(2572), [190, 144, 98]),
    "Digestive_DescendingColon": (FJ(2567), [180, 136, 92]),
    "Digestive_Rectum":          (FJ(2571), [170, 112, 90]),
    "Digestive_Liver":           (FJ(2816, 2409, *range(2818, 2825)), [140, 52, 46]),
    "Digestive_Gallbladder":     (FJ(2817), [72, 140, 82]),
    "Digestive_BileDucts":       (FJ(3079, 3080, 3096, 3123), [104, 172, 92]),
    "Digestive_Pancreas":        (FJ(1895, 2629), [236, 200, 130]),
}
CLIP_Z_MIN ={"Heart_InferiorVenaCava": 1160.0}
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
    for m in meshes.values():
        m.apply_translation(shift)
    center, radius, slender = model_frame([m.vertices for m in meshes.values()])
    for node, m in meshes.items():
        scene.add_geometry(m, node_name=node, geom_name=node)
        pos, nrm = anchor(m.vertices, center, radius, slender)
        hotspots[node] = {"position": pos, "normal": nrm, "triangles": int(len(m.faces))}
    path = f"{OUT}/{name}.glb"
    scene.export(path)
    size = (hi - lo) * 1
    print(f"{path}: {len(meshes)} nodes, size(m)={np.round(hi - lo, 3).tolist()}")
    json.dump(hotspots, open(f"{OUT}/{name}.hotspots.json", "w"), indent=1)

PACKS = {"spine": SPINE, "heart": HEART, "digestive": DIGESTIVE}
for name in sys.argv[3:] or PACKS:
    build(name, PACKS[name])
