import sys, os, re, shutil, numpy as np, trimesh, yaml
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf, Vt, UsdUtils
src, dst = sys.argv[1], sys.argv[2]
sc = trimesh.load(src)
pack = Path(dst).resolve().parent.parent
LABEL_H, LABEL_MIN_M = 0.06, 0.012
ACCENT, INK, CARD = (217, 119, 6, 255), (28, 25, 23, 255), (255, 255, 255, 235)

def label_png(text, path):
    try: font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 56)
    except OSError: font = ImageFont.load_default(56)
    H, pad, r = 88, 28, 12
    W = int(pad + 2 * r + 18 + font.getlength(text) + pad)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, W - 1, H - 1], radius=H // 2, fill=CARD, outline=(0, 0, 0, 60), width=2)
    d.ellipse([pad, H / 2 - r, pad + 2 * r, H / 2 + r], fill=ACCENT)
    d.text((pad + 2 * r + 18, H / 2), text, font=font, fill=INK, anchor="lm")
    img.save(path)
    return W / H, (pad + r) / W

def add_label(stage, prim, text, pos, facing, h, tex_dir):
    tex = tex_dir / f"{prim.rsplit('/', 1)[1]}.png"
    aspect, u_dot = label_png(text, tex)
    up = np.array([0.0, 1.0, 0.0]); f = facing / np.linalg.norm(facing); r = np.cross(up, f); w = h * aspect
    at = lambda u, v: pos + f * h * 0.6 + r * (u - u_dot) * w + up * (v - 0.5) * h
    quad = UsdGeom.Mesh.Define(stage, prim)
    quad.CreatePointsAttr([Gf.Vec3f(*at(u, v)) for u, v in [(0, 0), (1, 0), (1, 1), (0, 1)]])
    quad.CreateFaceVertexCountsAttr([4]); quad.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
    quad.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none); quad.CreateDoubleSidedAttr(False)
    UsdGeom.PrimvarsAPI(quad).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex).Set(
        [Gf.Vec2f(0, 0), Gf.Vec2f(1, 0), Gf.Vec2f(1, 1), Gf.Vec2f(0, 1)])
    mat = UsdShade.Material.Define(stage, prim + "_mat")
    st = UsdShade.Shader.Define(stage, prim + "_mat/st"); st.CreateIdAttr("UsdPrimvarReader_float2")
    st.CreateInput("varname", Sdf.ValueTypeNames.String).Set("st")
    tx = UsdShade.Shader.Define(stage, prim + "_mat/tex"); tx.CreateIdAttr("UsdUVTexture")
    tx.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(f"{tex_dir.name}/{tex.name}")
    tx.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st.ConnectableAPI(), "result")
    for wrap in ("wrapS", "wrapT"): tx.CreateInput(wrap, Sdf.ValueTypeNames.Token).Set("clamp")
    rgb = tx.CreateOutput("rgb", Sdf.ValueTypeNames.Float3); a = tx.CreateOutput("a", Sdf.ValueTypeNames.Float)
    sh = UsdShade.Shader.Define(stage, prim + "_mat/PBR"); sh.CreateIdAttr("UsdPreviewSurface")
    sh.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0, 0, 0))
    sh.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(rgb)
    sh.CreateInput("opacity", Sdf.ValueTypeNames.Float).ConnectToSource(a)
    sh.CreateInput("opacityThreshold", Sdf.ValueTypeNames.Float).Set(0.5)
    sh.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(1.0)
    mat.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(), "surface")
    UsdShade.MaterialBindingAPI.Apply(quad.GetPrim()).Bind(mat)
usda = dst[:-5] + ".usdc"
stage = Usd.Stage.CreateNew(usda)
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y); UsdGeom.SetStageMetersPerUnit(stage, 1.0)
root = UsdGeom.Xform.Define(stage, "/Root"); stage.SetDefaultPrim(root.GetPrim())
for name, m in sc.geometry.items():
    T = sc.graph.get(name)[0]; m = m.copy(); m.apply_transform(T)
    p = f"/Root/{re.sub(r'[^A-Za-z0-9_]', '_', name)}"
    mesh = UsdGeom.Mesh.Define(stage, p)
    mesh.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(m.vertices.astype(np.float32)))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray([3] * len(m.faces)))
    mesh.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(m.faces.astype(np.int32).ravel()))
    mesh.CreateNormalsAttr(Vt.Vec3fArray.FromNumpy(m.vertex_normals.astype(np.float32)))
    mesh.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
    mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none); mesh.CreateDoubleSidedAttr(True)
    c = np.asarray(m.visual.material.baseColorFactor[:3], float); c = c / 255 if c.max() > 1 else c
    mat = UsdShade.Material.Define(stage, p + "_mat")
    sh = UsdShade.Shader.Define(stage, p + "_mat/PBR"); sh.CreateIdAttr("UsdPreviewSurface")
    sh.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*c))
    sh.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.65)
    sh.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    mat.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(), "surface")
    UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(mat)
labels = 0
tex_dir = Path(usda).parent / "labels"
if (pack / "hotspots.yaml").exists():
    tex_dir.mkdir(exist_ok=True)
    names = {s["id"]: s["display_name_en"] for s in yaml.safe_load(open(pack / "structures.yaml", encoding="utf-8"))}
    h = max((sc.bounds[1][1] - sc.bounds[0][1]) * LABEL_H, LABEL_MIN_M)
    UsdGeom.Xform.Define(stage, "/Root/Labels")
    for hs in yaml.safe_load(open(pack / "hotspots.yaml", encoding="utf-8")) or []:
        pos = np.array([float(x.rstrip("m")) for x in hs["position"].split()])
        n = np.array([float(x) for x in hs["normal"].split()])
        sides = [n] if np.linalg.norm(n) > 0 else [np.array([0.0, 0, 1]), np.array([0.0, 0, -1])]
        for i, facing in enumerate(sides):
            add_label(stage, f"/Root/Labels/{re.sub(r'[^A-Za-z0-9_]', '_', hs['mesh_name'])}_{i}",
                      names.get(hs["structure_id"], hs["mesh_name"]), pos, facing, h, tex_dir)
            labels += 1
stage.GetRootLayer().Save()
ok = UsdUtils.CreateNewARKitUsdzPackage(Sdf.AssetPath(usda), dst)
os.remove(usda); shutil.rmtree(tex_dir, ignore_errors=True)
print(dst, "ok" if ok else "FAILED", os.path.getsize(dst), f"{labels} labels")
