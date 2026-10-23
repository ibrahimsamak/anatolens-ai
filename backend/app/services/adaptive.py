import uuid
import numpy as np
from sqlalchemy import select
from app.models.content import Structure
from app.models.learning import Progress, BanditEvent, Attempt, QuizQuestion
from app.rl.bandit import build_policy, rank
from app.rl.features import build_feature_vector
from app.services.quiz import generate_questions, grade

DIFFS = ["easy", "medium", "hard"]

def _actions(lesson_id, db) -> list[str]:
    sids = db.execute(select(Structure.id).where(Structure.lesson_id == lesson_id)).scalars().all()
    return [f"{s}|{d}" for s in sids for d in DIFFS]

def _load_policy(user_id, actions, db):
    events = db.execute(select(BanditEvent).where(BanditEvent.user_id == user_id)).scalars().all()
    return build_policy(actions, [(e.action, e.context_json["x"], e.reward) for e in events])

def _progress(user_id, structure_id, db) -> Progress:
    p = db.get(Progress, {"user_id": user_id, "structure_id": structure_id})
    return p or Progress(user_id=user_id, structure_id=structure_id, mastery=0.0, attempts=0)

def _contexts(user_id, actions, db) -> dict[str, np.ndarray]:
    progress = {}
    ctx = {}
    for action in actions:
        sid, diff = action.split("|")
        if sid not in progress:
            progress[sid] = _progress(user_id, sid, db)
        p = progress[sid]
        ctx[action] = build_feature_vector(p.mastery, p.attempts, diff)
    return ctx

def next_question(user_id, lesson_id, db) -> "QuizQuestion | None":
    actions = _actions(lesson_id, db)
    if not actions:
        return None
    contexts = _contexts(user_id, actions, db)
    for action in rank(_load_policy(user_id, actions, db), contexts):
        sid, diff = action.split("|")
        qs = generate_questions(lesson_id, sid, diff, db, n=1)
        if qs:
            db.add(BanditEvent(id=str(uuid.uuid4()), user_id=user_id, action=action,
                               context_json={"x": contexts[action].tolist()}, reward=0.0))
            db.commit()
            return qs[0]
    return None

def record_result(user_id, question_id, answer, db) -> dict:
    q = db.get(QuizQuestion, question_id)
    correct = grade(question_id, answer, db)
    p = _progress(user_id, q.structure_id, db)
    p.mastery = 0.7 * p.mastery + 0.3 * (1.0 if correct else 0.0)
    p.attempts += 1
    db.merge(p)
    db.add(Attempt(id=str(uuid.uuid4()), user_id=user_id, question_id=question_id, correct=int(correct)))
    ev = db.execute(select(BanditEvent).where(BanditEvent.user_id == user_id).order_by(BanditEvent.created_at.desc())).scalars().first()
    reward = 1.0 if correct else 0.0
    if ev: ev.reward = reward
    db.commit()
    return {"correct": correct, "mastery": p.mastery, "reward": reward}
