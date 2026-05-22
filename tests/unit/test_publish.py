# tests/unit/test_publish.py
import json
from pathlib import Path

import pytest

from src.publish import render_site


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
    templates = Path("templates")
    site = tmp_path / "site"
    return db, named, network, templates, site


def test_render_site_creates_files(setup):
    db, named, network, templates, site = setup
    render_site(
        named_path=named, network_path=network, db=db,
        templates_dir=templates, site_dir=site,
    )
    assert (site / "index.md").exists()
    assert (site / "domains" / "0.md").exists()
    assert (site / "articles" / "1.md").exists()
    assert (site / "network.html").exists()
