import json


def build_pairs(raw: list[dict]) -> list[dict]:
    out = []
    for r in raw:
        prompt, chosen, rejected = ((r.get(k) or "").strip() for k in ("prompt", "chosen", "rejected"))
        if prompt and chosen and rejected and chosen != rejected:
            out.append({"prompt": r["prompt"], "chosen": r["chosen"], "rejected": r["rejected"]})
    return out


def export_preferences(db, out_path: str) -> int:
    from app.models.learning import DpoPreference
    rows = [{"prompt": p.prompt, "chosen": p.chosen, "rejected": p.rejected}
            for p in db.query(DpoPreference).order_by(DpoPreference.created_at, DpoPreference.id)]
    pairs = build_pairs(rows)
    with open(out_path, "w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    return len(pairs)
