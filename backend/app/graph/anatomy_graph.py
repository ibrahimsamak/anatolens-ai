import os
import yaml
from rdflib import Graph, URIRef
from collections import deque
from app.core.logging import log

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

    def objects(self, node_id: str, predicate: str) -> set[str]:
        return {str(o).removeprefix(NS) for o in self.g.objects(self._uri(node_id), self._uri(predicate))}

    def add_edge(self, subject_id: str, predicate: str, object_id: str) -> None:
        self.g.add((self._uri(subject_id), self._uri(predicate), self._uri(object_id)))


def build_graph(*structures_yaml_paths: str) -> AnatomyGraph:
    g = Graph()
    data = []
    for path in structures_yaml_paths:
        with open(path, encoding="utf-8") as f:
            data += yaml.safe_load(f) or []
    for s in data:
        subj = URIRef(NS + s["id"])
        for rel, targets in (s.get("relations") or {}).items():
            pred = URIRef(NS + rel)
            for t in targets:
                g.add((subj, pred, URIRef(NS + t)))
    return AnatomyGraph(g)

def build_graph_backend(*paths: str):
    paths = [str(p) for p in paths] or ["../content/spine/structures.yaml"]
    if os.getenv("GRAPH_BACKEND", "rdflib") != "neo4j":
        return build_graph(*paths)
    try:
        from neo4j import GraphDatabase
        from app.graph.neo4j_graph import Neo4jAnatomyGraph, load_structures_into_neo4j
        driver = GraphDatabase.driver(os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                                      auth=("neo4j", os.getenv("NEO4J_PASSWORD", "anatolens")))
        driver.verify_connectivity()
        load_structures_into_neo4j(driver, *paths)
        return Neo4jAnatomyGraph(driver)
    except Exception as e:
        log.warning("neo4j_unavailable_fallback_rdflib", error=str(e))
        return build_graph(*paths)