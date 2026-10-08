from pathlib import Path
from app.graph.anatomy_graph import build_graph

SPINE_STRUCTURES = Path(__file__).resolve().parents[2] / "content" / "spine" / "structures.yaml"

def test_lumbar_neighbors_include_vertebral_column_and_sacral():
    g = build_graph(SPINE_STRUCTURES)
    n = g.neighbors("spine.lumbar_region", hops=1)
    assert "spine.vertebral_column" in n and "spine.sacral_region" in n

def test_unknown_node_returns_empty():
    g = build_graph(SPINE_STRUCTURES)
    assert g.neighbors("spine.not_real") == set()
