import numpy as np
from app.rl.bandit import build_policy, clean_reward, rank
from app.rl.features import build_feature_vector

X = np.array([0.1, 0.2, 0.5, 1.0])

def test_cold_start_returns_valid_ranking():
    mab = build_policy(["a", "b"], events=[])
    assert sorted(rank(mab, {"a": X, "b": X})) == ["a", "b"]

def test_converges_to_higher_reward_action():
    events = []
    for _ in range(100):
        events.append(("a", X, 1.0)); events.append(("b", X, 0.0))
    assert rank(build_policy(["a", "b"], events), {"a": X, "b": X})[0] == "a"

def test_bad_rewards_are_dropped_or_clamped():
    assert clean_reward(float("nan")) is None and clean_reward(float("inf")) is None and clean_reward(None) is None
    assert clean_reward(7.0) == 1.0 and clean_reward(-3.0) == 0.0 and clean_reward(0.4) == 0.4
    mab = build_policy(["a", "b"], [("a", X, float("nan")), ("a", X, 7.0), ("b", X, 0.0)])
    assert rank(mab, {"a": X, "b": X})[0] == "a"

def test_unknown_actions_in_history_are_skipped():
    mab = build_policy(["a"], [("removed_structure|hard", X, 1.0), ("a", X, 1.0)])
    assert rank(mab, {"a": X}) == ["a"]

def test_rank_scores_each_action_with_its_own_context():
    weak, strong = np.array([0.0, 0.1, 0.5, 1.0]), np.array([1.0, 0.5, 0.5, 1.0])
    events = []
    for _ in range(100):
        events += [("low", weak, 1.0), ("low", strong, 0.0), ("high", weak, 0.0), ("high", strong, 1.0)]
    mab = build_policy(["low", "high"], events, alpha=0.1)
    assert rank(mab, {"low": weak, "high": weak})[0] == "low"
    assert rank(mab, {"low": strong, "high": strong})[0] == "high"

def test_rank_returns_every_action_once():
    mab = build_policy(["a", "b", "c"], [])
    ctx = {a: build_feature_vector(0.0, 0, "easy") for a in ("a", "b", "c")}
    assert sorted(rank(mab, ctx)) == ["a", "b", "c"]
