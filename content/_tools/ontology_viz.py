import sys, json
from pathlib import Path
from collections import Counter
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTENT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT.parent / "demo" / "ontology.html"


def _load(p: Path):
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def lesson_data(d: Path) -> dict:
    lesson = _load(d / "lesson.yaml") if (d / "lesson.yaml").exists() else {}
    knowledge: dict[str, dict[str, dict[str, int]]] = {}
    for kf in sorted(d.glob("knowledge.*.yaml")):
        locale = kf.name.split(".")[1]
        counts = Counter((k["structure_id"], k.get("review_status", "DRAFT")) for k in _load(kf) or [])
        for (sid, status), n in counts.items():
            knowledge.setdefault(sid, {}).setdefault(locale, {})[status] = n
    nodes, links = [], []
    for s in _load(d / "structures.yaml"):
        nodes.append({"id": s["id"], "en": s.get("display_name_en", s["id"]), "ar": s.get("display_name_ar"),
                      "mesh": s.get("mesh_name"), "aliases": s.get("aliases") or [],
                      "knowledge": knowledge.get(s["id"], {})})
        for rel, targets in (s.get("relations") or {}).items():
            links += [{"s": s["id"], "t": t, "rel": rel} for t in targets]
    return {"id": lesson.get("id", d.name), "title": lesson.get("title", d.name), "nodes": nodes, "links": links}


def main():
    lessons = [lesson_data(d) for d in sorted(CONTENT.iterdir())
               if d.is_dir() and (d / "structures.yaml").exists()]
    data = json.dumps(lessons, ensure_ascii=False).replace("</", "<\\/")
    tpl = (Path(__file__).with_name("ontology_viz.html")).read_text(encoding="utf-8")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(tpl.replace("/*__DATA__*/[]", data), encoding="utf-8")
    print(f"wrote {OUT} ({len(lessons)} lessons)")


if __name__ == "__main__":
    main()
