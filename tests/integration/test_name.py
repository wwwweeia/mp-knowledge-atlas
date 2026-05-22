"""Integration tests for src.name — LLM naming stage with TF-IDF fallback."""

import json
from unittest.mock import patch

import pytest

from src.name import run_name


@pytest.mark.integration
def test_run_name_falls_back_to_tfidf_on_llm_failure(tmp_path):
    """When LLM fails, cluster should be named via TF-IDF keyword extraction."""
    clusters = {
        "method": "hdbscan",
        "items": [
            {"article_id": 1, "title": "Claude Code 实战", "cluster_id": 0},
            {"article_id": 2, "title": "Claude Code 工作流", "cluster_id": 0},
            {"article_id": 3, "title": "Claude Code 与 Cursor", "cluster_id": 0},
        ],
    }
    src = tmp_path / "clusters.json"
    src.write_text(json.dumps(clusters, ensure_ascii=False))
    out = tmp_path / "named.json"

    with patch("src.name.name_cluster", side_effect=ValueError("bad json")):
        run_name(in_path=src, out_path=out)

    data = json.loads(out.read_text())
    c = data["clusters"][0]
    assert c["fallback"] is True
    assert c["name"]
    assert sorted(c["article_ids"]) == [1, 2, 3]


@pytest.mark.integration
def test_run_name_uses_llm_when_available(tmp_path):
    """When LLM succeeds, cluster should use the LLM-generated name."""
    clusters = {"method": "hdbscan", "items": [
        {"article_id": 1, "title": "x", "cluster_id": 0},
        {"article_id": 2, "title": "y", "cluster_id": 0},
    ]}
    src = tmp_path / "c.json"
    src.write_text(json.dumps(clusters))
    out = tmp_path / "n.json"

    with patch("src.name.name_cluster",
               return_value={"name": "测试领域", "description": "desc"}):
        run_name(in_path=src, out_path=out)

    c = json.loads(out.read_text())["clusters"][0]
    assert c["name"] == "测试领域"
    assert c["fallback"] is False


@pytest.mark.integration
def test_run_name_skips_noise_cluster(tmp_path):
    """Items with cluster_id == -1 should be excluded from output."""
    clusters = {
        "method": "hdbscan",
        "items": [
            {"article_id": 1, "title": "real topic", "cluster_id": 0},
            {"article_id": 2, "title": "noise", "cluster_id": -1},
        ],
    }
    src = tmp_path / "clusters.json"
    src.write_text(json.dumps(clusters, ensure_ascii=False))
    out = tmp_path / "named.json"

    with patch("src.name.name_cluster",
               return_value={"name": "Real", "description": "d"}):
        run_name(in_path=src, out_path=out)

    data = json.loads(out.read_text())
    assert len(data["clusters"]) == 1
    assert data["clusters"][0]["article_ids"] == [1]


@pytest.mark.integration
def test_run_name_empty_clusters(tmp_path):
    """When all items are noise (cluster_id == -1), output should have empty list."""
    clusters = {
        "method": "hdbscan",
        "items": [
            {"article_id": 1, "title": "noise", "cluster_id": -1},
        ],
    }
    src = tmp_path / "clusters.json"
    src.write_text(json.dumps(clusters, ensure_ascii=False))
    out = tmp_path / "named.json"

    run_name(in_path=src, out_path=out)

    data = json.loads(out.read_text())
    assert data["clusters"] == []
