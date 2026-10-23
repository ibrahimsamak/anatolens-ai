from eval.runners.judge_eval import judge_pairwise

def test_judge_prefers_grounded_over_vague(monkeypatch):
    import eval.runners.judge_eval as J
    monkeypatch.setattr(J, "_ask_judge", lambda q, x, y: "A" if len(x) > len(y) else "B")
    better = "The lumbar region has five vertebrae (L1-L5) [1]."
    worse = "It is a back part."
    assert judge_pairwise("q", better, worse) == "A"   
    assert judge_pairwise("q", worse, better) == "B"

def test_position_biased_judge_is_a_tie(monkeypatch):
    import eval.runners.judge_eval as J
    monkeypatch.setattr(J, "_ask_judge", lambda q, x, y: "A")   
    assert judge_pairwise("q", "x", "y") == "TIE"
