# tests/unit/test_summarize.py
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.lib.db import (
    fetch_by_stage,
    init_db,
    upsert_articles,
    update_stage,
)
from src.summarize import run_summarize


@pytest.fixture
def db_with_cleaned(tmp_path):
    p = tmp_path / "test.db"
    init_db(p)
    articles = [
        {
            "source_id": "mp-001",
            "feed_id": "f1",
            "feed_name": "测试",
            "title": "AI文章",
            "url": None,
            "raw_html": "<p>content</p>",
            "published_at": None,
            "has_fulltext": 1,
        },
        {
            "source_id": "mp-002",
            "feed_id": "f1",
            "feed_name": "测试",
            "title": "已摘要文章",
            "url": None,
            "raw_html": None,
            "published_at": None,
            "has_fulltext": 0,
        },
    ]
    upsert_articles(p, articles)
    all_a = {a["source_id"]: a for a in fetch_by_stage(p, "ingested")}
    update_stage(p, all_a["mp-001"]["id"], "cleaned", clean_text="这是AI文章正文")
    update_stage(
        p, all_a["mp-002"]["id"], "summarized",
        summary="已摘要文章", keywords="[]",
    )
    return p


def test_run_summarize_processes_cleaned_articles(db_with_cleaned):
    mock_result = {"summary": "关于AI的技术文章", "keywords": ["AI", "技术"]}
    with patch("src.summarize.summarize_article", return_value=mock_result):
        count = run_summarize(db=db_with_cleaned)
    assert count == 1


def test_run_summarize_stores_summary(db_with_cleaned):
    mock_result = {"summary": "关于AI的技术文章", "keywords": ["AI", "技术"]}
    with patch("src.summarize.summarize_article", return_value=mock_result):
        run_summarize(db=db_with_cleaned)
    summarized = fetch_by_stage(db_with_cleaned, "summarized")
    by_title = {a["title"]: a for a in summarized}
    art = by_title["AI文章"]
    assert art["summary"] == "关于AI的技术文章"
    assert json.loads(art["keywords"]) == ["AI", "技术"]


def test_run_summarize_skips_already_summarized(db_with_cleaned):
    mock_result = {"summary": "x", "keywords": ["y"]}
    with patch("src.summarize.summarize_article", return_value=mock_result):
        count = run_summarize(db=db_with_cleaned)
    # mp-002 已经是 summarized 状态，不应该再处理
    summarized = fetch_by_stage(db_with_cleaned, "summarized")
    assert len(summarized) == 2  # mp-001 新增 + mp-002 已有
