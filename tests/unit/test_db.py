# tests/unit/test_db.py
import json
from pathlib import Path

import pytest

from src.lib.db import (
    fetch_all_articles,
    fetch_by_stage,
    init_db,
    mark_embedded,
    upsert_articles,
    update_stage,
)


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test.db"
    init_db(p)
    return p


def test_init_db_creates_table(db):
    """init_db should create the articles table without error."""
    from src.lib.db import get_conn
    with get_conn(db) as conn:
        rows = conn.execute("SELECT count(*) FROM articles").fetchone()
    assert rows[0] == 0


def test_upsert_articles_inserts_new(db):
    articles = [
        {
            "source_id": "mp-001",
            "feed_id": "feed-1",
            "feed_name": "阿里云开发者",
            "title": "测试文章",
            "url": "https://example.com/1",
            "raw_html": "<p>hello</p>",
            "published_at": "2026-01-01T00:00:00",
            "has_fulltext": 1,
        }
    ]
    count = upsert_articles(db, articles)
    assert count == 1
    result = fetch_all_articles(db)
    assert len(result) == 1
    assert result[0]["source_id"] == "mp-001"
    assert result[0]["pipeline_stage"] == "ingested"


def test_upsert_articles_skips_duplicates(db):
    articles = [
        {
            "source_id": "mp-001",
            "feed_id": "feed-1",
            "feed_name": "阿里云开发者",
            "title": "测试文章",
            "url": "https://example.com/1",
            "raw_html": None,
            "published_at": None,
            "has_fulltext": 0,
        }
    ]
    upsert_articles(db, articles)
    # 插入相同的 source_id 应该跳过
    articles[0]["title"] = "更新标题"
    count = upsert_articles(db, articles)
    assert count == 0
    result = fetch_all_articles(db)
    assert len(result) == 1
    assert result[0]["title"] == "测试文章"  # 未更新


def test_fetch_by_stage(db):
    articles = [
        {
            "source_id": "mp-001",
            "feed_id": "feed-1",
            "feed_name": "测试",
            "title": "文章1",
            "url": None,
            "raw_html": "<p>text</p>",
            "published_at": None,
            "has_fulltext": 1,
        },
        {
            "source_id": "mp-002",
            "feed_id": "feed-1",
            "feed_name": "测试",
            "title": "文章2",
            "url": None,
            "raw_html": None,
            "published_at": None,
            "has_fulltext": 0,
        },
    ]
    upsert_articles(db, articles)
    ingested = fetch_by_stage(db, "ingested")
    assert len(ingested) == 2


def test_update_stage(db):
    articles = [
        {
            "source_id": "mp-001",
            "feed_id": "feed-1",
            "feed_name": "测试",
            "title": "文章1",
            "url": None,
            "raw_html": "<p>text</p>",
            "published_at": None,
            "has_fulltext": 1,
        }
    ]
    upsert_articles(db, articles)
    aid = fetch_all_articles(db)[0]["id"]
    update_stage(db, aid, "cleaned", clean_text="cleaned text")
    result = fetch_by_stage(db, "cleaned")
    assert len(result) == 1
    assert result[0]["clean_text"] == "cleaned text"


def test_mark_embedded(db):
    articles = [
        {
            "source_id": "mp-001",
            "feed_id": "feed-1",
            "feed_name": "测试",
            "title": "文章1",
            "url": None,
            "raw_html": None,
            "published_at": None,
            "has_fulltext": 0,
        }
    ]
    upsert_articles(db, articles)
    aid = fetch_all_articles(db)[0]["id"]
    update_stage(db, aid, "summarized", summary="sum", keywords='["kw"]')
    mark_embedded(db, aid, "emb-001")
    result = fetch_all_articles(db)
    assert result[0]["embedding_id"] == "emb-001"
    assert result[0]["pipeline_stage"] == "embedded"
