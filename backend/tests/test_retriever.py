from app.rag.retriever import _rrf, _tokens

def test_rrf_rewards_agreement_between_rankers():
    dense, bm25 = ["A", "C", "D", "B"], ["D", "A", "B", "C"]
    fused = _rrf([dense, bm25])
    assert sorted(fused, key=fused.get, reverse=True) == ["A", "D", "C", "B"]
    assert abs(fused["A"] - (1 / 61 + 1 / 62)) < 1e-12

def test_rrf_counts_chunks_found_by_only_one_ranker():
    fused = _rrf([["A"], ["B", "A"]])
    assert fused["A"] > fused["B"] > 0

def test_tokens_strip_punctuation_and_keep_arabic():
    assert _tokens("Which vertebrae carry the most WEIGHT?") == ["which", "vertebrae", "carry", "the", "most", "weight"]
    assert _tokens("L1-L5") == ["l1", "l5"]
    assert _tokens("ما وظيفة العمود الفقري؟") == ["ما", "وظيفة", "العمود", "الفقري"]
