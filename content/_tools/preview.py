import sys, numpy as np, trimesh, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

src, dst = sys.argv[1], sys.argv[2]
sc = trimesh.load(src)
parts = []
for name, m in sc.geometry.items():
    m = m.copy(); m.apply_transform(sc.graph.get(name)[0])
    rgb = np.asarray(m.visual.material.baseColorFactor[:3], float); rgb = rgb / 255 if rgb.max() > 1 else rgb
    parts.append((m, rgb))
lo = np.min([m.bounds[0] for m, _ in parts], 0); hi = np.max([m.bounds[1] for m, _ in parts], 0)
mid, half = (lo + hi) / 2, (hi - lo).max() / 2
light = np.array([0.3, 0.5, 1.0]); light /= np.linalg.norm(light)

fig = plt.figure(figsize=(8, 5), dpi=100)
for i, (title, azim) in enumerate([("front (+Z)", -90), ("side", 0)]):
    ax = fig.add_subplot(1, 2, i + 1, projection="3d")
    for m, rgb in parts:
        tris = m.vertices[m.faces][:, :, [0, 2, 1]]
        shade = 0.45 + 0.55 * np.clip(m.face_normals[:, [0, 2, 1]] @ light[[0, 2, 1]], 0, 1)
        ax.add_collection3d(Poly3DCollection(tris, facecolors=np.clip(rgb * shade[:, None], 0, 1), linewidths=0))
    ax.set_xlim(mid[0] - half, mid[0] + half); ax.set_ylim(mid[2] - half, mid[2] + half); ax.set_zlim(mid[1] - half, mid[1] + half)
    ax.view_init(elev=8, azim=azim); ax.set_box_aspect((1, 1, 1), zoom=1.7); ax.set_axis_off(); ax.set_title(title, fontsize=10)
fig.savefig(dst, facecolor="white"); print(dst)
