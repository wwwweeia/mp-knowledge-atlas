# tests/unit/test_clean.py
from pathlib import Path

import pytest

from src.clean import run_clean
from src.lib.db import (
    fetch_all_articles,
    fetch_by_stage,
    init_db,
    upsert_articles,
    update_stage,
)


@pytest.fixture
def db_with_articles(tmp_path):
    p = tmp_path / "test.db"
    init_db(p)
    articles = [
        {
            "source_id": "mp-001",
            "feed_id": "f1",
            "feed_name": "测试",
            "title": "有全文的文章",
            "url": None,
            "raw_html": "<p>这是正文内容</p><script>bad</script>",
            "published_at": None,
            "has_fulltext": 1,
        },
        {
            "source_id": "mp-002",
            "feed_id": "f1",
            "feed_name": "测试",
            "title": "无全文的文章",
            "url": None,
            "raw_html": None,
            "published_at": None,
            "has_fulltext": 0,
        },
    ]
    upsert_articles(p, articles)
    return p


def test_run_clean_processes_fulltext_articles(db_with_articles):
    count = run_clean(db=db_with_articles)
    assert count == 1  # only 1 has fulltext


def test_run_clean_stores_clean_text(db_with_articles):
    run_clean(db=db_with_articles)
    cleaned = fetch_by_stage(db_with_articles, "cleaned")
    assert len(cleaned) == 1
    assert "这是正文内容" in cleaned[0]["clean_text"]
    assert "bad" not in cleaned[0]["clean_text"]


def test_run_clean_advances_no_fulltext_to_summarized(db_with_articles):
    run_clean(db=db_with_articles)
    all_articles = fetch_all_articles(db_with_articles)
    by_sid = {a["source_id"]: a for a in all_articles}
    assert by_sid["mp-002"]["pipeline_stage"] == "summarized"
    assert by_sid["mp-002"]["summary"] == "无全文的文章"
