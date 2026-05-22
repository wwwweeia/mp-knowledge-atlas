import sqlite3
from src.lib.db import (
    init_db, get_conn, insert_article, fetch_pending_embeddings,
    mark_embedded, fetch_all_articles
)

def test_init_db_creates_articles_table(tmp_path):
    db = tmp_path / "t.db"
    init_db(db)
    with sqlite3.connect(db) as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(articles)")}
    assert cols == {"id", "title", "url", "source", "source_name",
                    "manual_tag", "summary", "added_at", "embedding_id"}

def test_insert_and_fetch_pending(tmp_path):
    db = tmp_path / "t.db"
    init_db(db)
    with get_conn(db) as c:
        insert_article(c, title="A", url="u1", source="wechat",
                       source_name=None, manual_tag="ai-coding", summary=None)
        insert_article(c, title="B", url=None, source=None,
                       source_name=None, manual_tag=None, summary=None)
    pending = fetch_pending_embeddings(db)
    assert {p["title"] for p in pending} == {"A", "B"}

def test_mark_embedded(tmp_path):
    db = tmp_path / "t.db"
    init_db(db)
    with get_conn(db) as c:
        insert_article(c, title="A", url="u1", source="wechat",
                       source_name=None, manual_tag="ai-coding", summary=None)

    mark_embedded(db, 1, "emb_123")
    pending = fetch_pending_embeddings(db)
    assert len(pending) == 0

def test_fetch_all_articles(tmp_path):
    db = tmp_path / "t.db"
    init_db(db)
    with get_conn(db) as c:
        insert_article(c, title="A", url="u1", source="wechat",
                       source_name=None, manual_tag="ai-coding", summary=None)
        insert_article(c, title="B", url=None, source=None,
                       source_name=None, manual_tag=None, summary=None)

    articles = fetch_all_articles(db)
    assert len(articles) == 2
    assert {a["title"] for a in articles} == {"A", "B"}
