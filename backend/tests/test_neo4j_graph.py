from pathlib import Path
import pytest
from app.graph.anatomy_graph import AnatomyGraph, build_graph_backend

SPINE_STRUCTURES = str(Path(__file__).resolve().parents[2] / "content" / "spine" / "structures.yaml")


def test_neo4j_down_falls_back_to_rdflib(monkeypatch):
    monkeypatch.setenv("GRAPH_BACKEND", "neo4j")
    monkeypatch.setenv("NEO4J_URI", "bolt://127.0.0.1:1")   
    g = build_graph_backend(SPINE_STRUCTURES)
    assert isinstance(g, AnatomyGraph)
    assert "spine.vertebral_column" in g.neighbors("spine.lumbar_region", hops=1)


@pytest.mark.integration
def test_neo4j_neighbors_match_rdflib_contract():
    from neo4j import GraphDatabase
    from app.graph.anatomy_graph import build_graph
    from app.graph.neo4j_graph import Neo4jAnatomyGraph, load_structures_into_neo4j

    driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "anatolens"))
    load_structures_into_neo4j(driver, SPINE_STRUCTURES)
    g = Neo4jAnatomyGraph(driver)
    n = g.neighbors("spine.lumbar_region", hops=1)
    assert "spine.vertebral_column" in n and g.neighbors("spine.not_real") == set()
    assert isinstance(n, set) and "spine.lumbar_region" not in g.neighbors("spine.lumbar_region", hops=2)
    assert n == build_graph(SPINE_STRUCTURES).neighbors("spine.lumbar_region", hops=1)
    driver.close()
