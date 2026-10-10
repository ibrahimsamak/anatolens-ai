from pathlib import Path
from app.recognition.ontology import OntologyResolver

CONTENT = Path(__file__).resolve().parents[2] / "content"
RES = OntologyResolver.from_yaml(CONTENT / "spine" / "structures.yaml")

def test_alias_and_case_insensitive():
    assert RES.resolve("Lumbar") == "spine.lumbar_region"
    assert RES.resolve("L1-L5") == "spine.lumbar_region"

def test_unknown_label_returns_none():
    assert RES.resolve("Lmbar??") is None

def test_arabic_alias_resolves():
    assert RES.resolve("العمود الفقري") == "spine.vertebral_column"

def test_punctuation_only_label_returns_none():
    assert RES.resolve("??") is None

def test_heart_pack_loads_without_alias_collisions():
    assert OntologyResolver.from_yaml(CONTENT / "heart" / "structures.yaml").resolve("aorta") == "heart.aorta"
