# tests/unit/test_ingest.py
import sqlite3
from pathlib import Path

import pytest

from src.ingest import run_ingest


@pytest.fixture
def wemp_db(tmp_path):
    """模拟 We-MP-RSS 数据库结构."""
    db_path = tmp_path / "we_mp_rss.db"
    with sqlite3.connect(db_path) as c:
        c.executescript("""
            CREATE TABLE feeds (
                id TEXT PRIMARY KEY,
                mp_name TEXT NOT NULL
            );
            CREATE TABLE articles (
                id TEXT PRIMARY KEY,
                mp_id TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT,
                content TEXT,
                publish_time INTEGER,
                status INTEGER DEFAULT 1
            );
        """)
        c.execute("INSERT INTO feeds VALUES (?, ?)", ("feed-1", "阿里云开发者"))
        c.execute("INSERT INTO feeds VALUES (?, ?)", ("feed-2", "美团技术团队"))
        c.execute(
            "INSERT INTO articles VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("art-1", "feed-1", "文章A", "https://a.com", "<p>content</p>", 1700000000, 1),
        )
        c.execute(
            "INSERT INTO articles VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("art-2", "feed-2", "文章B", None, None, 1700000001, 1),
        )
        c.execute(
            "INSERT INTO articles VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("art-3", "feed-1", "活动文章", "https://c.com", "<p>event</p>", 1700000002, 1000),
        )
    return db_path


@pytest.fixture
def our_db(tmp_path):
    from src.lib.db import init_db
    p = tmp_path / "articles.db"
    init_db(p)
    return p


def test_run_ingest_imports_articles(wemp_db, our_db):
    new, backfill = run_ingest(wemp=wemp_db, db=our_db)
    assert new == 2  # art-3 status=1000, skipped
    assert backfill == 0


def test_run_ingest_sets_has_fulltext(wemp_db, our_db):
    run_ingest(wemp=wemp_db, db=our_db)
    from src.lib.db import fetch_all_articles
    articles = fetch_all_articles(our_db)
    by_sid = {a["source_id"]: a for a in articles}
    assert by_sid["art-1"]["has_fulltext"] == 1
    assert by_sid["art-2"]["has_fulltext"] == 0


def test_run_ingest_idempotent(wemp_db, our_db):
    run_ingest(wemp=wemp_db, db=our_db)
    new2, backfill2 = run_ingest(wemp=wemp_db, db=our_db)
    assert new2 == 0
    assert backfill2 == 0
    from src.lib.db import fetch_all_articles
    assert len(fetch_all_articles(our_db)) == 2


def test_backfill_detects_new_fulltext(tmp_path):
    """art-2 initially has no content, then gets fulltext — should be reset."""
    from src.lib.db import fetch_all_articles, init_db, update_stage

    # Setup: wemp DB where art-2 now has content
    wemp_path = tmp_path / "wemp.db"
    with sqlite3.connect(wemp_path) as c:
        c.executescript("""
            CREATE TABLE feeds (id TEXT PRIMARY KEY, mp_name TEXT);
            CREATE TABLE articles (
                id TEXT PRIMARY KEY, mp_id TEXT, title TEXT,
                url TEXT, content TEXT, publish_time INTEGER, status INTEGER
            );
        """)
        c.execute("INSERT INTO feeds VALUES ('feed-1', '测试')")
        c.execute("INSERT INTO articles VALUES ('art-1', 'feed-1', '文章A', 'https://a.com', '<p>c</p>', 1, 1)")
        c.execute("INSERT INTO articles VALUES ('art-2', 'feed-1', '文章B', NULL, '<p>new content</p>', 2, 1)")

    db_path = tmp_path / "articles.db"
    init_db(db_path)

    # First ingest: art-2 had no content (simulated by first import without content)
    from src.lib.db import upsert_articles
    upsert_articles(db_path, [
        {"source_id": "art-1", "feed_id": "feed-1", "feed_name": "测试",
         "title": "文章A", "url": "https://a.com", "raw_html": "<p>c</p>",
         "published_at": None, "has_fulltext": 1},
        {"source_id": "art-2", "feed_id": "feed-1", "feed_name": "测试",
         "title": "文章B", "url": None, "raw_html": None,
         "published_at": None, "has_fulltext": 0},
    ])
    # art-2 was processed without fulltext
    art2 = [a for a in fetch_all_articles(db_path) if a["source_id"] == "art-2"][0]
    update_stage(db_path, art2["id"], "summarized", summary="文章B", keywords="[]")

    # Second ingest: wemp now has content for art-2
    new, backfill = run_ingest(wemp=wemp_path, db=db_path)
    assert new == 0
    assert backfill == 1

    art2_updated = [a for a in fetch_all_articles(db_path) if a["source_id"] == "art-2"][0]
    assert art2_updated["has_fulltext"] == 1
    assert art2_updated["raw_html"] == "<p>new content</p>"
    assert art2_updated["pipeline_stage"] == "ingested"
