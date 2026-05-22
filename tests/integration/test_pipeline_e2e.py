# tests/integration/test_pipeline_e2e.py
"""End-to-end pipeline test with mocked external services."""

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest


@pytest.fixture
def wemp_db(tmp_path):
    db = tmp_path / "wemp.db"
    with sqlite3.connect(db) as c:
        c.executescript("""
            CREATE TABLE feeds (id TEXT PRIMARY KEY, mp_name TEXT);
            CREATE TABLE articles (
                id TEXT PRIMARY KEY, mp_id TEXT, title TEXT,
                url TEXT, content TEXT, publish_time INTEGER, status INTEGER
            );
        """)
        c.execute("INSERT INTO feeds VALUES ('f1', '测试公众号')")
        for i in range(20):
            c.execute(
                "INSERT INTO articles VALUES (?, ?, ?, ?, ?, ?, ?)",
                (f"art-{i}", "f1", f"文章{i}", f"https://x.com/{i}",
                 f"<p>正文内容{i}</p>", 1700000000 + i, 1),
            )
    return db


@pytest.fixture
def paths(tmp_path):
    return {
        "wemp": tmp_path / "wemp.db",
        "db": tmp_path / "articles.db",
        "chroma": tmp_path / "chroma",
        "out": tmp_path / "out",
        "site": tmp_path / "site",
    }


def test_full_pipeline(wemp_db, paths):
    """Run all stages: ingest -> clean -> summarize -> embed -> cluster -> network -> publish."""
    fake_vecs = [np.random.rand(128).tolist() for _ in range(20)]
    fake_name = {"name": "测试领域", "description": "自动测试", "keywords": ["测试"]}
    fake_summary = {"summary": "文章摘要", "keywords": ["技术"]}

    with (
        patch("src.embed.embed_texts", return_value=fake_vecs),
        patch("src.lib.llm.name_cluster", return_value=fake_name),
        patch("src.lib.llm.summarize_article", return_value=fake_summary),
    ):
        from src.ingest import run_ingest
        from src.clean import run_clean
        from src.summarize import run_summarize
        from src.embed import run_embed
        from src.cluster import run_cluster
        from src.network import run_network
        from src.publish import generate_data_json

        # Stage 1: ingest
        new, backfill = run_ingest(wemp=wemp_db, db=paths["db"])
        assert new == 20
        assert backfill == 0

        # Stage 2: clean (all articles have HTML content)
        n = run_clean(db=paths["db"])
        assert n == 20

        # Stage 3: summarize
        n = run_summarize(db=paths["db"])
        assert n == 20

        # Stage 4: embed
        n = run_embed(db=paths["db"], chroma_path=paths["chroma"])
        assert n == 20

        # Stage 5: cluster
        out_path = paths["out"] / "clusters_named.json"
        result = run_cluster(
            chroma_path=paths["chroma"], db=paths["db"], out_path=out_path,
        )
        assert len(result["clusters"]) >= 1

        # Stage 6: network
        net_path = paths["out"] / "network.json"
        net = run_network(
            named_path=out_path, chroma_path=paths["chroma"], out_path=net_path,
        )
        assert "nodes" in net
        assert "edges" in net

        # Stage 7: publish
        data_json_path = paths["out"] / "data.json"
        generate_data_json(
            named_path=out_path, network_path=net_path, db=paths["db"],
            output_path=data_json_path,
        )
        assert data_json_path.exists()
        data = json.loads(data_json_path.read_text())
        assert "stats" in data
        assert "domains" in data
        assert "network" in data
        assert data["stats"]["total_articles"] == 20
