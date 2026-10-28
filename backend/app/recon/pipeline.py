import io, uuid
from functools import lru_cache
import numpy as np
import trimesh
from PIL import Image
from app.models.graph_ops import MeshCandidate
from app.recon.validate import validate_mesh


@lru_cache
def _depth_model():
    from transformers import pipeline
    return pipeline("depth-estimation", model="LiheYoung/depth-anything-small-hf")


def reconstruct(image_bytes, out_glb, lesson_id):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    depth = _depth_model()(img)["depth"]
    depth.thumbnail((256, 256))
    d = np.array(depth, dtype=float)
    ys, xs = np.mgrid[0:d.shape[0], 0:d.shape[1]]
    points = np.stack([xs.ravel(), ys.ravel(), d.ravel()], axis=1)
    try:
        trimesh.points.PointCloud(points).convex_hull.export(out_glb)
        ok, reason = validate_mesh(out_glb)
    except Exception as e:
        ok, reason = False, f"reconstruction failed: {e}"
    return MeshCandidate(id=str(uuid.uuid4()), lesson_id=lesson_id, glb_path=out_glb,
                         status="AI_GENERATED" if ok else "DRAFT", reason=reason)
