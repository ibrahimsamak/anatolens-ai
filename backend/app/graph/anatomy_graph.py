import yaml
from rdflib import Graph, URIRef
from collections import deque

NS = "https://anatolens.ai/anatomy#"

class AnatomyGraph:
    def __init__(self, g: Graph): 
        self.g = g
    
    def _uri(self, nid: str)-> URIRef:
        return URIRef(NS + nid)
    
    def neighbors(self, node_id: str, hops:int = 1)-> set[str]:
        start = self._uri(node_id)
        if(start, None, None) not in self.g and (None, None, start) not in self.g:
            return set()
        seen, frontier = set(), deque([(start, 0)])
        while(frontier):
            node, d = frontier.popleft()
            if d >= hops:
                continue
            for _, _, o in self.g.triples((node, None, None)):
                if isinstance(o, URIRef) and o != start and str(o).startswith(NS):
                    nid = str(o).removeprefix(NS)
                    if nid not in seen:
                        seen.add(nid)
                        frontier.append((o, d + 1))
            for s,_,_ in self.g.triples((None, None, node)):
                if s != start and str(s).startswith(NS):
                    nid = str(s).removeprefix(NS)
                    if nid not in seen:
                        seen.add(nid)
                        frontier.append((s, d + 1))
        return seen


def build_graph(structures_yaml_path: str) -> AnatomyGraph:
    g = Graph()
    with open(structures_yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    for s in data:
        subj = URIRef(NS + s["id"])
        for rel, targets in (s.get("relations") or {}).items():
            pred = URIRef(NS + rel)
            for t in targets:
                g.add((subj, pred, URIRef(NS + t)))
    return AnatomyGraph(g)