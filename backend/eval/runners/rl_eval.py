from collections import defaultdict
import numpy as np
from sqlalchemy import select
from app.models.content import Structure
from app.models.learning import Attempt, BanditEvent, QuizQuestion
from app.rl.bandit import build_policy, rank
from app.rl.features import build_feature_vector
from app.services.adaptive import DIFFS

def _progress_at(attempts, t) -> dict[str, tuple[float, int]]:
    p = {}
    for at, sid, correct in attempts:
        if at >= t:
            break
        m, n = p.get(sid, (0.0, 0))
        p[sid] = (0.7 * m + 0.3 * (1.0 if correct else 0.0), n + 1)
    return p


def _answered(event, next_event, attempts) -> bool:
    end = next_event.created_at if next_event else None
    return any(at >= event.created_at and (end is None or at < end) for at, _, _ in attempts)


def replay(events, attempts, lesson_structures, test_share: float = 0.2) -> dict:
    test_ids = {e.id for e in events[int(len(events) * (1 - test_share)):]}
    by_user = defaultdict(list)
    for e in events:
        by_user[e.user_id].append(e)
    scored, matched, unanswered = [], [], 0
    for user, evs in by_user.items():
        hist = attempts.get(user, [])
        for i, e in enumerate(evs):
            sid = e.action.split("|")[0]
            if e.id not in test_ids or sid not in lesson_structures:
                continue
            if not _answered(e, evs[i + 1] if i + 1 < len(evs) else None, hist):
                unanswered += 1
                continue
            sids = lesson_structures[sid]
            mab = build_policy([f"{s}|{d}" for s in sids for d in DIFFS], [(p.action, p.context_json["x"], p.reward) for p in evs[:i]])
            prog = _progress_at(hist, e.created_at)
            ctx = {f"{s}|{d}": build_feature_vector(*prog.get(s, (0.0, 0)), d) for s in sids for d in DIFFS}
            scored.append(e.reward)
            if rank(mab, ctx)[0] == e.action:
                matched.append(e.reward)
    if not scored:
        return {"uplift_vs_logged": 0.0, "n": 0, "matched": 0, "unanswered": unanswered}
    logged = float(np.mean(scored))
    pol = float(np.mean(matched)) if matched else logged
    return {"uplift_vs_logged": pol - logged, "n": len(scored), "matched": len(matched), "unanswered": unanswered}


def run_rl_eval(cfg, db, test_share: float = 0.2) -> dict:
    events = db.execute(select(BanditEvent).order_by(BanditEvent.created_at)).scalars().all()
    attempts = defaultdict(list)
    q = (select(Attempt.user_id, Attempt.created_at, QuizQuestion.structure_id, Attempt.correct).join(QuizQuestion, Attempt.question_id == QuizQuestion.id).order_by(Attempt.created_at))
    for user, at, sid, correct in db.execute(q):
        attempts[user].append((at, sid, correct))
    rows = db.execute(select(Structure.id, Structure.lesson_id)).all()
    lessons = defaultdict(list)
    for sid, lid in rows:
        lessons[lid].append(sid)
    return replay(events, attempts, {sid: lessons[lid] for sid, lid in rows}, test_share)
