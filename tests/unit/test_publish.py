# tests/unit/test_publish.py
import json
from pathlib import Path

import pytest

from src.publish import generate_data_json


@pytest.fixture
def setup(tmp_path):
    db = tmp_path / "articles.db"
    from src.lib.db import init_db, upsert_articles, update_stage
    init_db(db)
    articles = [
        {
            "source_id": "mp-001",
            "feed_id": "f1",
            "feed_name": "阿里云开发者",
            "title": "AI技术",
            "url": "https://example.com",
            "raw_html": None,
            "published_at": "2026-01-01T00:00:00",
            "has_fulltext": 0,
        },
    ]
    upsert_articles(db, articles)
    from src.lib.db import fetch_by_stage
    a = fetch_by_stage(db, "ingested")[0]
    update_stage(db, a["id"], "summarized", summary="AI摘要", keywords='["AI"]')

    named = tmp_path / "clusters_named.json"
    named.write_text(json.dumps({
        "method": "kmeans",
        "clusters": [{
            "cluster_id": 0,
            "name": "人工智能",
            "description": "AI相关技术",
            "keywords": ["AI", "深度学习"],
            "article_ids": [a["id"]],
            "top_articles": [{"id": a["id"], "title": "AI技术", "summary": "AI摘要"}],
        }],
    }))
    network = tmp_path / "network.json"
    network.write_text(json.dumps({
        "nodes": [{"cluster_id": 0, "name": "人工智能", "size": 1}],
        "edges": [],
        "bridges": [{"cluster_id": 0, "betweenness": 1.0}],
    }))
    output = tmp_path / "data.json"
    return db, named, network, output


def test_generate_data_json_creates_file(setup):
    db, named, network, output = setup
    generate_data_json(
        named_path=named, network_path=network, db=db, output_path=output,
    )
    assert output.exists()


def test_generate_data_json_structure(setup):
    db, named, network, output = setup
    generate_data_json(
        named_path=named, network_path=network, db=db, output_path=output,
    )
    data = json.loads(output.read_text())

    assert "stats" in data
    assert data["stats"]["total_articles"] == 1
    assert data["stats"]["total_domains"] == 1
    assert data["stats"]["bridge_domains"] == 1
    assert data["stats"]["sources"] == 1

    assert "domains" in data
    assert len(data["domains"]) == 1
    domain = data["domains"][0]
    assert domain["id"] == 0
    assert domain["name"] == "人工智能"
    assert domain["description"] == "AI相关技术"
    assert domain["article_count"] == 1
    assert domain["keywords"] == ["AI", "深度学习"]
    assert domain["is_bridge"] is True
    assert domain["betweenness"] == 1.0
    assert len(domain["articles"]) == 1
    assert domain["articles"][0]["title"] == "AI技术"
    assert domain["articles"][0]["source"] == "阿里云开发者"

    assert "network" in data
    assert len(data["network"]["nodes"]) == 1
    assert len(data["network"]["edges"]) == 0

    assert "recent_articles" in data
    assert len(data["recent_articles"]) == 1


def test_generate_data_json_network_edges(setup, tmp_path):
    db, named, network, output = setup
    network.write_text(json.dumps({
        "nodes": [
            {"cluster_id": 0, "name": "人工智能", "size": 1},
            {"cluster_id": 1, "name": "大数据", "size": 2},
        ],
        "edges": [{"source": 0, "target": 1, "weight": 0.85}],
        "bridges": [{"cluster_id": 0, "betweenness": 1.0}],
    }))
    generate_data_json(
        named_path=named, network_path=network, db=db, output_path=output,
    )
    data = json.loads(output.read_text())
    assert len(data["network"]["edges"]) == 1
    edge = data["network"]["edges"][0]
    assert edge["source"] == 0
    assert edge["target"] == 1
    assert edge["weight"] == 0.85
