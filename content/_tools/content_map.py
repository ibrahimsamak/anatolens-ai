import sys, json, base64
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTENT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT.parent / "demo" / "content_map.html"
INGEST = ROOT.parent / "backend" / "app" / "content" / "ingest.py"
EXPECTED = ["lesson.yaml", "structures.yaml", "knowledge.en.yaml", "knowledge.ar.yaml", "hotspots.yaml", "quiz.yaml"]
CONSUMERS = {
    "lesson.yaml": "ingest.py → lessons table",
    "structures.yaml": "ingest.py → structures table · AnatomyGraph · OntologyResolver",
    "knowledge.en.yaml": "ingest.py → knowledge_chunks (pgvector, locale=en)",
    "knowledge.ar.yaml": "ingest.py → knowledge_chunks (pgvector, locale=ar)",
    "hotspots.yaml": "demo <model-viewer> hotspot buttons",
    "quiz.yaml": "quiz service (not built yet)",
}


def _load(p: Path):
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def glb_nodes(p: Path) -> list[str] | None:
    b = p.read_bytes()
    if b[:4] != b"glTF":
        return None
    n = int.from_bytes(b[12:16], "little")
    return [x["name"] for x in json.loads(b[20:20 + n]).get("nodes", []) if x.get("name")]


def lesson_pack(d: Path, ingest_src: str) -> dict:
    lesson = _load(d / "lesson.yaml")
    structures = _load(d / "structures.yaml") or []
    hotspots = _load(d / "hotspots.yaml") if (d / "hotspots.yaml").exists() else []
    knowledge = {kf.name.split(".")[1]: _load(kf) or [] for kf in sorted(d.glob("knowledge.*.yaml"))}
    assets = sorted((d / "assets").iterdir()) if (d / "assets").exists() else []
    glb = next((a for a in assets if a.suffix == ".glb"), None)
    nodes = glb_nodes(glb) if glb else None
    preview = next((a for a in assets if a.name.endswith("_preview.png")), None)

    files = [{"name": n, "exists": (d / n).exists(), "size": (d / n).stat().st_size if (d / n).exists() else 0,
              "use": CONSUMERS.get(n, ""), "ingested": n in ingest_src if n != "hotspots.yaml" else None}
             for n in EXPECTED]
    files += [{"name": f"assets/{a.name}", "exists": True, "size": a.stat().st_size, "ingested": None,
               "use": {".glb": "lesson.model_url (Android / web)", ".usdz": "lesson.ios_model_url (iOS Quick Look)",
                       ".png": "recognition test fixture (conftest)", ".md": "model licence"}.get(a.suffix, "")}
              for a in assets]

    ids = {s["id"] for s in structures}
    checks = []
    add = lambda level, msg, sid=None: checks.append({"level": level, "msg": msg, "sid": sid})
    for url_key in ("model_url", "ios_model_url"):
        name = (lesson.get(url_key) or "").rsplit("/", 1)[-1]
        if name and not (d / "assets" / name).exists():
            add("error", f"lesson.{url_key} points to {name}, which is not in assets/")
    for f in files:
        if not f["exists"]:
            add("info", f"{f['name']} not authored yet ({f['use']})")
        elif f["ingested"] is False:
            add("error", f"{f['name']} exists but ingest.py never loads it")
    hs_by = {h["structure_id"]: h for h in hotspots}
    for h in hotspots:
        if h["structure_id"] not in ids:
            add("error", f"hotspots.yaml references unknown structure {h['structure_id']}")
    for s in structures:
        sid, mesh = s["id"], s.get("mesh_name")
        if mesh is None:
            add("info", "mesh_name is null: no 3D hotspot", sid)
        else:
            if nodes is not None and mesh not in nodes:
                add("error", f"mesh {mesh} is not a node in {glb.name}", sid)
            if sid not in hs_by:
                add("warn", f"has mesh {mesh} but no entry in hotspots.yaml", sid)
            elif hs_by[sid].get("mesh_name") != mesh:
                add("error", f"hotspot mesh {hs_by[sid].get('mesh_name')} ≠ structure mesh {mesh}", sid)
        for t in (t for ts in (s.get("relations") or {}).values() for t in ts):
            if t not in ids:
                add("error", f"relation target {t} is not a structure", sid)
        for loc, chunks in knowledge.items():
            if not any(c["structure_id"] == sid and c.get("review_status") == "APPROVED" for c in chunks):
                add("warn", f"no APPROVED knowledge in {loc}: tutor relies on neighbours or says 'no verified info'", sid)
    for loc, chunks in knowledge.items():
        for c in chunks:
            if c["structure_id"] not in ids:
                add("error", f"knowledge.{loc}.yaml references unknown structure {c['structure_id']}")
        pending = sum(1 for c in chunks if c.get("reviewer") in (None, "pending"))
        if pending:
            add("info", f"knowledge.{loc}.yaml: {pending}/{len(chunks)} chunks have reviewer pending (dev seed)")

    return {
        "dir": d.name, "lesson": lesson, "files": files, "glb": glb.name if glb else None, "glbNodes": nodes,
        "preview": "data:image/png;base64," + base64.b64encode(preview.read_bytes()).decode() if preview else None,
        "structures": [{"id": s["id"], "en": s.get("display_name_en", s["id"]), "ar": s.get("display_name_ar"),
                        "mesh": s.get("mesh_name"), "aliases": s.get("aliases") or [],
                        "relations": s.get("relations") or {}} for s in structures],
        "hotspots": hotspots, "knowledge": knowledge, "checks": checks,
    }


def main():
    ingest_src = INGEST.read_text(encoding="utf-8") if INGEST.exists() else ""
    packs = [lesson_pack(d, ingest_src) for d in sorted(CONTENT.iterdir())
             if d.is_dir() and (d / "lesson.yaml").exists()]
    data = json.dumps(packs, ensure_ascii=False).replace("</", "<\\/")
    tpl = Path(__file__).with_name("content_map.html").read_text(encoding="utf-8")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(tpl.replace("/*__DATA__*/[]", data), encoding="utf-8")
    for p in packs:
        counts = {lvl: sum(c["level"] == lvl for c in p["checks"]) for lvl in ("error", "warn", "info")}
        print(f"{p['dir']}: {len(p['structures'])} structures, checks {counts}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
