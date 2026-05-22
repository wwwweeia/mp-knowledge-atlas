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
    count = run_ingest(wemp=wemp_db, db=our_db)
    assert count == 2  # art-3 status=1000, skipped


def test_run_ingest_sets_has_fulltext(wemp_db, our_db):
    run_ingest(wemp=wemp_db, db=our_db)
    from src.lib.db import fetch_all_articles
    articles = fetch_all_articles(our_db)
    by_sid = {a["source_id"]: a for a in articles}
    assert by_sid["art-1"]["has_fulltext"] == 1
    assert by_sid["art-2"]["has_fulltext"] == 0


def test_run_ingest_idempotent(wemp_db, our_db):
    run_ingest(wemp=wemp_db, db=our_db)
    count2 = run_ingest(wemp=wemp_db, db=our_db)
    assert count2 == 0
    from src.lib.db import fetch_all_articles
    assert len(fetch_all_articles(our_db)) == 2
