import re, yaml

def _norm(s: str) -> str:
    return " ".join(re.sub(r"[^\w ]", "", s.lower()).split())

class OntologyResolver:
    def __init__(self, alias_to_id: dict[str, str]):
        self._map = alias_to_id

    @classmethod
    def from_yaml(cls, path: str) -> "OntologyResolver":
        m: dict[str, str] = {}
        with open(path, encoding="utf-8") as f:
            structures = yaml.safe_load(f)
        for s in structures:
            keys = [s["id"], s["display_name_en"], *s.get("aliases", [])]
            for k in keys:
                n = _norm(k)
                if not n:
                    continue
                if m.get(n, s["id"]) != s["id"]:
                    raise ValueError(f"alias {k!r} maps to both {m[n]} and {s['id']}")
                m[n] = s["id"]
        return cls(m)

    def resolve(self, label: str) -> str | None:
        return self._map.get(_norm(label))
