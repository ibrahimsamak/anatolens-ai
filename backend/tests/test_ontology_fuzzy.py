from pathlib import Path
from app.recognition.ontology import OntologyResolver

CONTENT = Path(__file__).resolve().parents[2] / "content"
RES = OntologyResolver.from_yaml(CONTENT / "spine" / "structures.yaml")

def test_near_miss_maps_above_floor():
    assert RES.resolve_fuzzy("Lumber") == "spine.lumbar_region"   

def test_exact_match_still_wins():
    assert RES.resolve_fuzzy("L1-L5") == "spine.lumbar_region"

def test_too_far_returns_none():
    assert RES.resolve_fuzzy("kidney") is None

def test_empty_or_punctuation_returns_none():
    assert RES.resolve_fuzzy("") is None
    assert RES.resolve_fuzzy("??") is None

def test_tie_between_two_structures_returns_none():
    res = OntologyResolver({"abcd": "x.one", "abce": "x.two"})
    assert res.resolve_fuzzy("abcf", floor=0.5) is None
