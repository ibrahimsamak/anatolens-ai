import math
import numpy as np
from mabwiser.mab import MAB, LearningPolicy

def clean_reward(reward) -> float | None:
    if reward is None or not math.isfinite(reward):
        return None
    return min(max(float(reward), 0.0), 1.0)

def build_policy(actions: list[str], events, dim: int = 4, alpha: float = 0.5) -> MAB:
    decisions, rewards, contexts = [], [], []
    for action, x, r in events:
        r = clean_reward(r)
        if action in actions and r is not None:
            decisions.append(action); rewards.append(r); contexts.append(np.asarray(x, dtype=float))
    mab = MAB(arms=list(actions), learning_policy=LearningPolicy.LinUCB(alpha=alpha))
    mab.fit(decisions, rewards, np.array(contexts).reshape(-1, dim))
    return mab

def rank(mab: MAB, contexts: dict[str, np.ndarray]) -> list[str]:
    actions = list(contexts)
    rows = mab.predict_expectations(np.array([contexts[a] for a in actions]))
    if isinstance(rows, dict):
        rows = [rows]
    score = {a: row[a] for a, row in zip(actions, rows)}
    return sorted(actions, key=score.__getitem__, reverse=True)
