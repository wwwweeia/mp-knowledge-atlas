"""Tests for src.embed — embedding pipeline stage."""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.embed import _text_for, run_embed
from src.lib.db import (
    fetch_by_stage,
    init_db,
    mark_embedded,
    update_stage,
    upsert_articles,
)


@pytest.fixture
def db_with_summarized(tmp_path):
    p = tmp_path / "test.db"
    init_db(p)
    articles = [
        {
            "source_id": "mp-001",
            "feed_id": "f1",
            "feed_name": "测试",
            "title": "AI技术文章",
            "url": None,
            "raw_html": None,
            "published_at": None,
            "has_fulltext": 0,
        },
    ]
    upsert_articles(p, articles)
    a = fetch_by_stage(p, "ingested")[0]
    update_stage(
        p,
        a["id"],
        "summarized",
        summary="关于AI的技术摘要",
        keywords='["AI"]',
    )
    return p


def test_text_for_combines_title_and_summary():
    row = {"title": "AI技术", "summary": "这是摘要"}
    result = _text_for(row)
    assert "AI技术" in result
    assert "这是摘要" in result


def test_text_for_title_only():
    row = {"title": "只有标题", "summary": None}
    result = _text_for(row)
    assert result == "只有标题"


def test_text_for_skips_duplicate_summary():
    row = {"title": "相同内容", "summary": "相同内容"}
    result = _text_for(row)
    assert result == "相同内容"


def test_run_embed_processes_summarized(db_with_summarized, tmp_path):
    chroma = tmp_path / "chroma"
    fake_vecs = [[0.1] * 128]
    with patch("src.embed.embed_texts", return_value=fake_vecs):
        count = run_embed(db=db_with_summarized, chroma_path=chroma)
    assert count == 1
