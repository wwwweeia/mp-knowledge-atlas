"""Tests for src.cluster — clustering + naming pipeline stage."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.cluster import cluster_vectors, run_cluster


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


@pytest.fixture
def setup(tmp_path):
    chroma = tmp_path / "chroma"
    out = tmp_path / "clusters_named.json"
    return chroma, out


def test_run_cluster_writes_named_output(setup):
    chroma, out = setup
    fake_vecs = np.random.rand(10, 128).tolist()
    fake_metas = [
        {"article_id": str(i), "title": f"文章{i}"}
        for i in range(10)
    ]
    mock_name_result = {
        "name": "AI技术",
        "description": "人工智能相关技术",
        "keywords": ["AI", "深度学习"],
    }
    with (
        patch("src.cluster.VecStore") as MockStore,
        patch("src.cluster.name_cluster", return_value=mock_name_result),
        patch("src.cluster.fetch_all_articles", return_value=[]),
    ):
        mock_instance = MagicMock()
        mock_instance.fetch_with_meta.return_value = (
            [f"id-{i}" for i in range(10)],
            fake_vecs,
            fake_metas,
        )
        MockStore.return_value = mock_instance
        result = run_cluster(chroma_path=chroma, db=Path(":memory:"), out_path=out)

    assert "clusters" in result
    assert result["clusters"][0]["name"] == "AI技术"
    assert "keywords" in result["clusters"][0]
    assert out.exists()


def test_run_cluster_handles_single_cluster(setup):
    chroma, out = setup
    # All vectors identical — HDBSCAN puts them in one cluster
    fake_vecs = [[0.1] * 128] * 10
    fake_metas = [
        {"article_id": str(i), "title": f"文章{i}"}
        for i in range(10)
    ]
    with (
        patch("src.cluster.VecStore") as MockStore,
        patch(
            "src.cluster.name_cluster",
            return_value={"name": "测试", "description": "desc", "keywords": []},
        ),
        patch("src.cluster.fetch_all_articles", return_value=[]),
    ):
        mock_instance = MagicMock()
        mock_instance.fetch_with_meta.return_value = (
            [f"id-{i}" for i in range(10)],
            fake_vecs,
            fake_metas,
        )
        MockStore.return_value = mock_instance
        result = run_cluster(chroma_path=chroma, db=Path(":memory:"), out_path=out)

    assert len(result["clusters"]) >= 1
