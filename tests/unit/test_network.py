import numpy as np
import pytest
from src.network import compute_bridges, compute_edges


@pytest.mark.unit
def test_compute_edges_topk_aggregates_similarities():
    vecs = {
        1: np.array([1.0, 0.0]),
        2: np.array([0.95, 0.05]),
        3: np.array([0.0, 1.0]),
        4: np.array([0.05, 0.95]),
    }
    clusters = [
        {"cluster_id": 0, "article_ids": [1, 2]},
        {"cluster_id": 1, "article_ids": [3, 4]},
    ]
    edges = compute_edges(clusters, vecs, top_k=1)
    e = next(x for x in edges if {x["source"], x["target"]} == {0, 1})
    assert 0.0 <= e["weight"] < 1.0


@pytest.mark.unit
def test_compute_bridges_returns_top_three():
    nodes = [0, 1, 2, 3]
    edges = [
        {"source": 0, "target": 1, "weight": 1.0},
        {"source": 1, "target": 2, "weight": 1.0},
        {"source": 2, "target": 3, "weight": 1.0},
    ]
    bridges = compute_bridges(nodes, edges, top_n=2)
    assert len(bridges) == 2
    assert {b["cluster_id"] for b in bridges} >= {1, 2}


@pytest.mark.unit
def test_compute_edges_skips_empty_clusters():
    vecs = {1: np.array([1.0, 0.0]), 3: np.array([0.0, 1.0])}
    clusters = [
        {"cluster_id": 0, "article_ids": [1]},
        {"cluster_id": 1, "article_ids": [99]},  # no vector
        {"cluster_id": 2, "article_ids": [3]},
    ]
    edges = compute_edges(clusters, vecs, top_k=1)
    # Only edge between 0 and 2 should exist (cluster 1 has no vectors)
    pair_set = {(e["source"], e["target"]) for e in edges}
    assert (0, 1) not in pair_set
    assert (1, 2) not in pair_set
    assert (0, 2) in pair_set


@pytest.mark.unit
def test_compute_bridges_single_node_returns_itself():
    bridges = compute_bridges(nodes=[0], edges=[], top_n=3)
    assert len(bridges) == 1
    assert bridges[0]["cluster_id"] == 0
    assert bridges[0]["betweenness"] == 0.0
