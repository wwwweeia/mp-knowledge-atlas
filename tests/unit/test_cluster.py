import numpy as np
import pytest
from src.cluster import cluster_vectors


def _two_blobs(n=12, dim=4, seed=0):
    rng = np.random.default_rng(seed)
    a = rng.normal(loc=0.0, scale=0.05, size=(n, dim))
    b = rng.normal(loc=5.0, scale=0.05, size=(n, dim))
    return np.vstack([a, b]).tolist()


@pytest.mark.unit
def test_hdbscan_finds_two_clusters_on_clean_blobs():
    vecs = _two_blobs()
    labels, method = cluster_vectors(vecs, min_cluster_size=3)
    distinct = {l for l in labels if l != -1}
    assert len(distinct) == 2
    assert method == "hdbscan"


@pytest.mark.unit
def test_kmeans_fallback_triggers_when_too_noisy():
    rng = np.random.default_rng(1)
    vecs = rng.normal(size=(20, 4)).tolist()
    labels, method = cluster_vectors(vecs, min_cluster_size=5)
    assert method == "kmeans"
    assert -1 not in labels
    assert len(set(labels)) >= 2
