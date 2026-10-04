import sys, os, re, numpy as np, trimesh
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf, Vt, UsdUtils
src, dst = sys.argv[1], sys.argv[2]
sc = trimesh.load(src)
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
stage.GetRootLayer().Save()
ok = UsdUtils.CreateNewARKitUsdzPackage(Sdf.AssetPath(usda), dst)
os.remove(usda); print(dst, "ok" if ok else "FAILED", os.path.getsize(dst))
