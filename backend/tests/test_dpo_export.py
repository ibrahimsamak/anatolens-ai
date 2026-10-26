import json, uuid
import pytest
from app.rl.dpo_export import build_pairs, export_preferences


def test_identical_chosen_rejected_is_skipped():
    rows = build_pairs([{"prompt": "q", "chosen": "same", "rejected": "same"},
                        {"prompt": "q2", "chosen": "good", "rejected": "bad"}])
    assert len(rows) == 1 and rows[0]["chosen"] == "good"

def test_whitespace_only_difference_is_skipped():
    assert build_pairs([{"prompt": "q", "chosen": "same ", "rejected": " same"}]) == []

def test_empty_or_missing_fields_are_skipped():
    assert build_pairs([{"prompt": "q", "chosen": "", "rejected": "bad"},
                        {"prompt": "q", "chosen": "good", "rejected": None},
                        {"prompt": "", "chosen": "good", "rejected": "bad"},
                        {"chosen": "good", "rejected": "bad"}]) == []


@pytest.mark.integration
def test_export_writes_jsonl(tmp_path):
    from app.db.session import SessionLocal
    from app.models.learning import DpoPreference
    ids = [f"test_{uuid.uuid4().hex}" for _ in range(2)]
    with SessionLocal() as db:
        db.add_all([DpoPreference(id=ids[0], prompt="what does L1 do?", chosen="good", rejected="bad"),
                    DpoPreference(id=ids[1], prompt="dup", chosen="same", rejected="same")])
        db.commit()
        try:
            out = tmp_path / "dpo.jsonl"
            n = export_preferences(db, str(out))
            lines = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
            assert n == len(lines)
            assert {"prompt": "what does L1 do?", "chosen": "good", "rejected": "bad"} in lines
            assert all(l["chosen"] != l["rejected"] for l in lines)
        finally:
            db.query(DpoPreference).filter(DpoPreference.id.in_(ids)).delete()
            db.commit()
