import numpy as np
import pytest
from app.models.learning import BanditEvent, Progress, QuizQuestion
from app.rl.bandit import build_policy, rank
from app.rl.features import build_feature_vector
from app.services import adaptive

ACTIONS = [f"spine.{s}|{d}" for s in ("lumbar_region", "sacral_region") for d in adaptive.DIFFS]

class FakeDB:
    def __init__(self): self.added = []
    def add(self, obj): self.added.append(obj)
    def commit(self): pass

def _question(sid, diff):
    return QuizQuestion(id=f"{sid}|{diff}", lesson_id="spine_001", structure_id=sid, difficulty=diff,
                        prompt="?", correct="5", choices=["3", "4", "5", "6"], review_status="APPROVED")

@pytest.fixture
def world(monkeypatch):
    state = {"events": [],
             "mastery": {"spine.lumbar_region": (0.9, 10), "spine.sacral_region": (0.1, 2)},
             "has_content": set(ACTIONS), "asked": [], "actions": list(ACTIONS)}
    monkeypatch.setattr(adaptive, "_actions", lambda lesson_id, db: state["actions"])
    monkeypatch.setattr(adaptive, "_load_policy", lambda user_id, actions, db: build_policy(actions, state["events"]))
    monkeypatch.setattr(adaptive, "_progress", lambda user_id, sid, db: Progress(
        user_id=user_id, structure_id=sid, mastery=state["mastery"][sid][0], attempts=state["mastery"][sid][1]))
    def fake_generate(lesson_id, sid, diff, db, n=1):
        state["asked"].append(f"{sid}|{diff}")
        return [_question(sid, diff)] if f"{sid}|{diff}" in state["has_content"] else []
    monkeypatch.setattr(adaptive, "generate_questions", fake_generate)
    return state

def _expected_best(state):
    return rank(build_policy(ACTIONS, state["events"]), adaptive._contexts("u1", ACTIONS, None))[0]

def _logged(db):
    return [o for o in db.added if isinstance(o, BanditEvent)]

def test_choice_depends_on_each_structures_mastery(world):
    for sid in ("spine.lumbar_region", "spine.sacral_region"):
        for _ in range(50):
            world["events"] += [(f"{sid}|hard", build_feature_vector(0.9, 10, "hard"), 1.0),
                                (f"{sid}|hard", build_feature_vector(0.1, 2, "hard"), 0.0),
                                (f"{sid}|easy", build_feature_vector(0.1, 2, "easy"), 1.0),
                                (f"{sid}|easy", build_feature_vector(0.9, 10, "easy"), 0.0)]
    q = adaptive.next_question("u1", "spine_001", FakeDB())
    assert (q.structure_id, q.difficulty) == ("spine.lumbar_region", "hard")

    world["mastery"]["spine.lumbar_region"] = (0.1, 2)
    q = adaptive.next_question("u1", "spine_001", FakeDB())
    assert q.difficulty == "easy"

def test_logged_context_is_the_one_used_to_choose(world):
    db = FakeDB()
    q = adaptive.next_question("u1", "spine_001", db)
    [ev] = _logged(db)
    assert ev.action == f"{q.structure_id}|{q.difficulty}" == _expected_best(world)
    mastery, attempts = world["mastery"][q.structure_id]
    assert np.allclose(ev.context_json["x"], build_feature_vector(mastery, attempts, q.difficulty))
    assert all(type(v) is float for v in ev.context_json["x"])

def test_falls_back_to_next_best_action_with_content(world):
    best = _expected_best(world)
    world["has_content"].discard(best)
    db = FakeDB()
    q = adaptive.next_question("u1", "spine_001", db)
    assert world["asked"][0] == best and f"{q.structure_id}|{q.difficulty}" != best
    [ev] = _logged(db)
    assert ev.action == f"{q.structure_id}|{q.difficulty}"

def test_no_approved_content_returns_none_and_logs_nothing(world):
    world["has_content"].clear()
    db = FakeDB()
    assert adaptive.next_question("u1", "spine_001", db) is None
    assert db.added == []

def test_lesson_without_structures_returns_none(world):
    world["actions"] = []
    assert adaptive.next_question("u1", "no_such_lesson", FakeDB()) is None
