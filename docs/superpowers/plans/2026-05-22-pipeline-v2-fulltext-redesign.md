# Pipeline V2 全文重写 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重写 pipeline，从 We-MP-RSS 导入文章全文，通过 HTML 清洗 + LLM 摘要提升嵌入质量，改善聚类、命名和网络图效果。

**Architecture:** 7 阶段 pipeline：ingest → clean → summarize → embed → cluster → network → publish。每阶段通过 `pipeline_stage` 字段跟踪进度，支持增量重跑。数据源从手工 markdown 切换到 We-MP-RSS SQLite。

**Tech Stack:** Python 3.12+, Ollama (nomic-embed-text), DeepSeek API, ChromaDB, HDBSCAN, NetworkX, BeautifulSoup4, Jinja2, VitePress + D3.js

---

## 文件映射

| 操作 | 文件 | 职责 |
|------|------|------|
| 重写 | `src/lib/db.py` | 新 schema（source_id, feed_name, raw_html, clean_text, summary, keywords, pipeline_stage） |
| 新建 | `src/ingest.py` | 从 We-MP-RSS 导入文章 |
| 新建 | `src/lib/html.py` | HTML 清洗工具函数 |
| 新建 | `src/clean.py` | HTML→纯文本 stage |
| 新建 | `src/summarize.py` | LLM 结构化摘要 stage |
| 扩展 | `src/lib/llm.py` | 新增 `summarize_article()` 函数 |
| 重写 | `src/embed.py` | 用 title+summary 嵌入 |
| 重写 | `src/cluster.py` | 合并 name.py，聚类+命名一体化 |
| 小改 | `src/lib/vec.py` | collection 名改为 `articles_v2` |
| 小改 | `src/network.py` | 适配新数据格式 |
| 重写 | `src/publish.py` | 增强：摘要、关键词、源信息 |
| 重写 | `templates/*.j2` | 展示摘要、关键词、公众号来源 |
| 重写 | `Makefile` | 新的 refresh 流程 |
| 更新 | `pyproject.toml` | 新增 beautifulsoup4/lxml，移除 jieba |
| 删除 | `src/name.py` | 合并到 cluster.py |
| 删除 | `src/lib/parse.py` | 不再解析 markdown |
| 删除 | `src/lib/tfidf_fallback.py` | 不再需要 |
| 删除 | `scripts/migrate_markdown.py` | 不再需要 |
| 删除 | `tests/unit/test_parse.py` | 对应删除 |
| 删除 | `tests/unit/test_tfidf_fallback.py` | 对应删除 |
| 重写 | 所有测试文件 | 适配新 pipeline |

---

## Phase 1: 基础层（db + ingest）

### Task 1: 重写 `src/lib/db.py` — 新数据模型

**Files:**
- Rewrite: `src/lib/db.py`
- Rewrite: `tests/unit/test_db.py`

- [ ] **Step 1: 写失败测试**

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/unit/test_db.py -v`
Expected: FAIL（函数不存在）

- [ ] **Step 3: 实现 `src/lib/db.py`**

```python
# src/lib/db.py
"""SQLite data layer for pipeline V2."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id              INTEGER PRIMARY KEY,
    source_id       TEXT NOT NULL UNIQUE,
    feed_id         TEXT NOT NULL,
    feed_name       TEXT NOT NULL,
    title           TEXT NOT NULL,
    url             TEXT,
    raw_html        TEXT,
    published_at    DATETIME,
    clean_text      TEXT,
    summary         TEXT,
    keywords        TEXT,
    embedding_id    TEXT,
    has_fulltext    BOOLEAN DEFAULT 0,
    pipeline_stage  TEXT DEFAULT 'ingested',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_source ON articles(source_id);
CREATE INDEX IF NOT EXISTS idx_pipeline ON articles(pipeline_stage);
CREATE INDEX IF NOT EXISTS idx_feed ON articles(feed_id);
CREATE INDEX IF NOT EXISTS idx_embedding ON articles(embedding_id);
"""

STAGE_ORDER = ["ingested", "cleaned", "summarized", "embedded"]


def init_db(path: Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as c:
        c.executescript(SCHEMA)


@contextmanager
def get_conn(path: Path):
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def upsert_articles(path: Path, articles: list[dict]) -> int:
    """Insert new articles, skip duplicates by source_id. Returns count inserted."""
    if not articles:
        return 0
    inserted = 0
    with get_conn(path) as c:
        for a in articles:
            try:
                c.execute(
                    "INSERT INTO articles "
                    "(source_id, feed_id, feed_name, title, url, raw_html, "
                    "published_at, has_fulltext) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        a["source_id"], a["feed_id"], a["feed_name"],
                        a["title"], a.get("url"), a.get("raw_html"),
                        a.get("published_at"), a.get("has_fulltext", 0),
                    ),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                pass
    return inserted


def fetch_by_stage(path: Path, stage: str) -> list[dict]:
    with get_conn(path) as c:
        rows = c.execute(
            "SELECT * FROM articles WHERE pipeline_stage = ?", (stage,)
        ).fetchall()
    return [dict(r) for r in rows]


def update_stage(
    path: Path, article_id: int, stage: str, **fields
) -> None:
    """Advance article to next pipeline stage, optionally updating fields."""
    sets = ["pipeline_stage = ?", "updated_at = CURRENT_TIMESTAMP"]
    vals = [stage]
    for key in ("clean_text", "summary", "keywords"):
        if key in fields:
            sets.append(f"{key} = ?")
            vals.append(fields[key])
    vals.append(article_id)
    with get_conn(path) as c:
        c.execute(
            f"UPDATE articles SET {', '.join(sets)} WHERE id = ?", vals
        )


def mark_embedded(path: Path, article_id: int, embedding_id: str) -> None:
    with get_conn(path) as c:
        c.execute(
            "UPDATE articles SET embedding_id = ?, pipeline_stage = 'embedded', "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (embedding_id, article_id),
        )


def fetch_pending_embeddings(path: Path) -> list[dict]:
    with get_conn(path) as c:
        rows = c.execute(
            "SELECT id, title, summary FROM articles "
            "WHERE pipeline_stage = 'summarized' AND embedding_id IS NULL"
        ).fetchall()
    return [dict(r) for r in rows]


def fetch_all_articles(path: Path) -> list[dict]:
    with get_conn(path) as c:
        rows = c.execute("SELECT * FROM articles").fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/unit/test_db.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add src/lib/db.py tests/unit/test_db.py
git commit -m "refactor(db): rewrite schema for pipeline V2 with fulltext support"
```

---

### Task 2: 新建 `src/ingest.py` — 从 We-MP-RSS 导入

**Files:**
- Create: `src/ingest.py`
- Create: `tests/unit/test_ingest.py`

- [ ] **Step 1: 写失败测试**

```python
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
                name TEXT NOT NULL
            );
            CREATE TABLE articles (
                id TEXT PRIMARY KEY,
                feed_id TEXT NOT NULL,
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/unit/test_ingest.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 `src/ingest.py`**

```python
# src/ingest.py
"""Ingest stage: import articles from We-MP-RSS SQLite."""

import argparse
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from src.lib.db import init_db, upsert_articles


def _fetch_wemp_articles(wemp_path: Path) -> list[dict]:
    """Read articles from We-MP-RSS database."""
    with sqlite3.connect(wemp_path) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT a.id, a.title, a.url, a.content, a.publish_time, "
            "a.feed_id, f.name AS feed_name "
            "FROM articles a "
            "JOIN feeds f ON a.feed_id = f.id "
            "WHERE a.status = 1"
        ).fetchall()

    articles = []
    for r in rows:
        content = r["content"]
        has_fulltext = 1 if content and len(content) > 100 else 0
        published = None
        if r["publish_time"]:
            try:
                published = datetime.fromtimestamp(r["publish_time"]).isoformat()
            except (OSError, ValueError):
                pass
        articles.append({
            "source_id": r["id"],
            "feed_id": r["feed_id"],
            "feed_name": r["feed_name"],
            "title": r["title"],
            "url": r["url"],
            "raw_html": content if has_fulltext else None,
            "published_at": published,
            "has_fulltext": has_fulltext,
        })
    return articles


def run_ingest(*, wemp: Path, db: Path) -> int:
    """Import new articles from We-MP-RSS. Returns count of newly inserted."""
    init_db(db)
    articles = _fetch_wemp_articles(wemp)
    return upsert_articles(db, articles)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--wemp",
        default=os.environ.get(
            "WEMP_DB", "/Users/wqw/Documents/idea_work/tools/we-mp-rss/data/we_mp_rss.db"
        ),
    )
    ap.add_argument(
        "--db", default=os.environ.get("DB_PATH", "data/articles.db")
    )
    a = ap.parse_args()
    n = run_ingest(wemp=Path(a.wemp), db=Path(a.db))
    print(f"ingested={n}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/unit/test_ingest.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add src/ingest.py tests/unit/test_ingest.py
git commit -m "feat(ingest): import articles from We-MP-RSS SQLite"
```

---

## Phase 2: 内容处理（clean + summarize）

### Task 3: 新建 `src/lib/html.py` — HTML 清洗工具

**Files:**
- Create: `src/lib/html.py`
- Create: `tests/unit/test_html.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_html.py
from src.lib.html import clean_html, extract_text


def test_clean_html_strips_scripts():
    html = '<p>Hello</p><script>alert("xss")</script><p>World</p>'
    result = clean_html(html)
    assert "alert" not in result
    assert "Hello" in result
    assert "World" in result


def test_clean_html_removes_footer_cta():
    html = '<p>正文内容</p><p>长按关注公众号</p><p>扫码关注</p>'
    result = clean_html(html)
    assert "长按关注" not in result
    assert "扫码关注" not in result
    assert "正文内容" in result


def test_clean_html_truncates_long_text():
    html = "<p>" + "A" * 20000 + "</p>"
    result = clean_html(html)
    assert len(result) <= 10100


def test_extract_text_returns_plain_text():
    html = "<div><h1>标题</h1><p>段落1</p><p>段落2</p></div>"
    result = extract_text(html)
    assert "标题" in result
    assert "段落1" in result
    assert "<" not in result


def test_extract_text_preserves_code_blocks():
    html = "<pre><code>def foo():\n    pass</code></pre>"
    result = extract_text(html)
    assert "def foo" in result
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/unit/test_html.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 `src/lib/html.py`**

```python
# src/lib/html.py
"""HTML cleaning utilities for WeChat public account articles."""

import re

from bs4 import BeautifulSoup

MAX_TEXT_LENGTH = 10000

FOOTER_PATTERNS = [
    re.compile(r"长按.{0,4}关注"),
    re.compile(r"扫码.{0,4}关注"),
    re.compile(r"点击.{0,6}在看"),
    re.compile(r"分享.{0,4}朋友圈"),
    re.compile(r"更多精彩.*关注"),
    re.compile(r"点赞.*在看.*分享"),
]


def _remove_footer_ctas(text: str) -> str:
    """Remove call-to-action footer lines common in WeChat articles."""
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        if any(p.search(line) for p in FOOTER_PATTERNS):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def clean_html(html: str) -> str:
    """Clean raw HTML: strip scripts, ads, footers. Return plain text."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    text = _remove_footer_ctas(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]
    return text


def extract_text(html: str) -> str:
    """Alias for clean_html, for readability in call sites."""
    return clean_html(html)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/unit/test_html.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add src/lib/html.py tests/unit/test_html.py
git commit -m "feat(html): add HTML cleaning utilities for WeChat articles"
```

---

### Task 4: 新建 `src/clean.py` — HTML 清洗阶段

**Files:**
- Create: `src/clean.py`
- Create: `tests/unit/test_clean.py`

- [ ] **Step 1: 写失败测试**

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/unit/test_clean.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 `src/clean.py`**

```python
# src/clean.py
"""Clean stage: convert HTML to plain text for articles with full content."""

import argparse
import os
from pathlib import Path

from src.lib.db import fetch_by_stage, init_db, update_stage
from src.lib.html import clean_html


def run_clean(*, db: Path) -> int:
    """Process ingested articles with fulltext. Returns count cleaned."""
    init_db(db)
    articles = fetch_by_stage(db, "ingested")
    if not articles:
        return 0

    cleaned = 0
    for a in articles:
        if a["has_fulltext"] and a.get("raw_html"):
            text = clean_html(a["raw_html"])
            update_stage(db, a["id"], "cleaned", clean_text=text)
            cleaned += 1
        else:
            update_stage(
                db, a["id"], "summarized",
                summary=a["title"], keywords="[]",
            )
    return cleaned


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("DB_PATH", "data/articles.db"))
    a = ap.parse_args()
    n = run_clean(db=Path(a.db))
    print(f"cleaned={n}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/unit/test_clean.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add src/clean.py tests/unit/test_clean.py
git commit -m "feat(clean): HTML-to-text pipeline stage"
```

---

### Task 5: 扩展 `src/lib/llm.py` — 新增摘要函数

**Files:**
- Modify: `src/lib/llm.py`
- Modify: `tests/unit/test_llm.py`

- [ ] **Step 1: 写失败测试（追加到现有 test_llm.py）**

```python
# tests/unit/test_llm.py（追加以下测试）
from unittest.mock import MagicMock

from src.lib.llm import summarize_article, name_cluster


class TestSummarizeArticle:
    def test_returns_summary_and_keywords(self):
        mock_resp = MagicMock()
        mock_resp.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"summary": "关于AI的测试摘要", "keywords": ["AI", "测试"]}'
                )
            )
        ]
        client = MagicMock()
        client.chat.completions.create.return_value = mock_resp
        result = summarize_article("文章标题", "这是文章正文", client=client)
        assert result["summary"] == "关于AI的测试摘要"
        assert result["keywords"] == ["AI", "测试"]

    def test_handles_non_technical(self):
        mock_resp = MagicMock()
        mock_resp.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"summary": "招聘信息", "keywords": ["招聘", "非技术"]}'
                )
            )
        ]
        client = MagicMock()
        client.chat.completions.create.return_value = mock_resp
        result = summarize_article("招聘", "岗位要求...", client=client)
        assert "非技术" in result["keywords"]

    def test_raises_on_bad_json(self):
        mock_resp = MagicMock()
        mock_resp.choices = [
            MagicMock(message=MagicMock(content="not json at all"))
        ]
        client = MagicMock()
        client.chat.completions.create.return_value = mock_resp
        with pytest.raises(ValueError):
            summarize_article("标题", "正文", client=client)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/unit/test_llm.py::TestSummarizeArticle -v`
Expected: FAIL（`summarize_article` 不存在）

- [ ] **Step 3: 在 `src/lib/llm.py` 追加 `summarize_article`**

在 `src/lib/llm.py` 文件末尾追加：

```python
SUMMARIZE_PROMPT = """\
请对以下技术文章生成结构化摘要。输出严格的 JSON 格式：
{{"summary": "200字以内的中文摘要", "keywords": ["关键词1", "关键词2", "关键词3"]}}

要求：
- summary 准确概括文章的核心内容和技术要点
- keywords 是 3-5 个最能代表文章主题的词
- 如果文章是活动/招聘/公告类非技术内容，keywords 中包含"非技术"

文章标题：{title}
文章正文：
{text}"""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    retry=retry_if_exception_type((APIConnectionError, RateLimitError)),
    reraise=True,
)
def summarize_article(
    title: str, text: str, *, client: OpenAI | None = None
) -> dict:
    cli = client or get_client()
    prompt = SUMMARIZE_PROMPT.format(title=title, text=text[:8000])
    resp = cli.chat.completions.create(
        model=MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    content = resp.choices[0].message.content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return JSON: {content!r}") from e
```

同时在文件顶部 import 中确保有 `import pytest`（如果测试文件需要）— 不需要，pytest 只在测试文件中。

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/unit/test_llm.py -v`
Expected: 全部 PASS（包括旧的 name_cluster 测试）

- [ ] **Step 5: 提交**

```bash
git add src/lib/llm.py tests/unit/test_llm.py
git commit -m "feat(llm): add summarize_article for structured article summaries"
```

---

### Task 6: 新建 `src/summarize.py` — LLM 摘要阶段

**Files:**
- Create: `src/summarize.py`
- Create: `tests/unit/test_summarize.py`

- [ ] **Step 1: 写失败测试**

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/unit/test_summarize.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 `src/summarize.py`**

```python
# src/summarize.py
"""Summarize stage: generate structured summaries via LLM."""

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from src.lib.db import fetch_by_stage, init_db, update_stage
from src.lib.llm import summarize_article


def run_summarize(*, db: Path, batch_size: int = 10) -> int:
    """Summarize cleaned articles with fulltext via LLM. Returns count processed."""
    init_db(db)
    cleaned = fetch_by_stage(db, "cleaned")
    if not cleaned:
        return 0

    done = 0
    for a in cleaned:
        text = a.get("clean_text") or ""
        if not text.strip():
            update_stage(
                db, a["id"], "summarized",
                summary=a["title"], keywords="[]",
            )
            done += 1
            continue
        try:
            result = summarize_article(a["title"], text)
            update_stage(
                db, a["id"], "summarized",
                summary=result["summary"],
                keywords=json.dumps(result["keywords"], ensure_ascii=False),
            )
        except Exception as e:
            print(f"[summarize] article {a['id']} failed: {e}")
            update_stage(
                db, a["id"], "summarized",
                summary=a["title"], keywords="[]",
            )
        done += 1
    return done


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("DB_PATH", "data/articles.db"))
    ap.add_argument("--batch-size", type=int, default=10)
    a = ap.parse_args()
    n = run_summarize(db=Path(a.db), batch_size=a.batch_size)
    print(f"summarized={n}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/unit/test_summarize.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add src/summarize.py tests/unit/test_summarize.py
git commit -m "feat(summarize): LLM structured summary stage"
```

---

## Phase 3: ML pipeline（embed + cluster + network）

### Task 7: 重写 `src/embed.py` — 用 title+summary 嵌入

**Files:**
- Rewrite: `src/embed.py`
- Rewrite: `tests/unit/test_embedding.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_embedding.py
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.embed import _text_for, run_embed
from src.lib.db import (
    fetch_by_stage,
    init_db,
    mark_embedded,
    upsert_articles,
    update_stage,
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
        p, a["id"], "summarized",
        summary="关于AI的技术摘要", keywords='["AI"]',
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


def test_run_embed_processes_summarized(db_with_summarized, tmp_path):
    chroma = tmp_path / "chroma"
    fake_vecs = [[0.1] * 128]
    with patch("src.embed.embed_texts", return_value=fake_vecs):
        count = run_embed(db=db_with_summarized, chroma_path=chroma)
    assert count == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/unit/test_embedding.py -v`
Expected: FAIL（新的 `run_embed` 签名不匹配）

- [ ] **Step 3: 重写 `src/embed.py`**

```python
# src/embed.py
"""Embed stage: generate vector embeddings from title + summary."""

import argparse
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv

from src.lib.db import fetch_pending_embeddings, init_db, mark_embedded
from src.lib.embedding import embed_texts
from src.lib.vec import VecStore


def _text_for(row: dict) -> str:
    title = row["title"]
    summary = row.get("summary")
    if summary and summary != title:
        return f"{title}\n\n{summary}"
    return title


def run_embed(*, db: Path, chroma_path: Path, batch_size: int = 32) -> int:
    """Embed summarized articles. Returns count embedded."""
    init_db(db)
    pending = fetch_pending_embeddings(db)
    if not pending:
        return 0

    store = VecStore(chroma_path)
    done = 0

    for i in range(0, len(pending), batch_size):
        batch = pending[i : i + batch_size]
        texts = [_text_for(r) for r in batch]
        try:
            vecs = embed_texts(texts)
        except Exception as e:
            print(f"[embed] batch failed: {e}")
            continue

        ids = [uuid.uuid4().hex for _ in batch]
        metas = [
            {"article_id": str(r["id"]), "title": r["title"]}
            for r in batch
        ]
        store.add(ids=ids, embeddings=vecs, metadatas=metas)

        for r, eid in zip(batch, ids):
            mark_embedded(db, r["id"], eid)
        done += len(batch)

    return done


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("DB_PATH", "data/articles.db"))
    ap.add_argument("--chroma", default=os.environ.get("CHROMA_PATH", "data/chroma"))
    a = ap.parse_args()
    n = run_embed(db=Path(a.db), chroma_path=Path(a.chroma))
    print(f"embedded={n}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/unit/test_embedding.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add src/embed.py tests/unit/test_embedding.py
git commit -m "refactor(embed): use title+summary for embeddings"
```

---

### Task 8: 更新 `src/lib/vec.py` — collection 名改为 v2

**Files:**
- Modify: `src/lib/vec.py`

- [ ] **Step 1: 修改 collection 名**

将 `COLLECTION = "articles_v1"` 改为 `COLLECTION = "articles_v2"`

```python
COLLECTION = "articles_v2"
```

- [ ] **Step 2: 运行 vec 相关测试**

Run: `uv run pytest tests/unit/test_vec.py -v`
Expected: PASS

- [ ] **Step 3: 提交**

```bash
git add src/lib/vec.py
git commit -m "refactor(vec): use articles_v2 collection for new pipeline"
```

---

### Task 9: 重写 `src/cluster.py` — 聚类 + 命名一体化

**Files:**
- Rewrite: `src/cluster.py`
- Rewrite: `tests/unit/test_cluster.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_cluster.py
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.cluster import run_cluster


@pytest.fixture
def setup(tmp_path):
    chroma = tmp_path / "chroma"
    out = tmp_path / "clusters_named.json"
    return chroma, out


def test_run_cluster_writes_named_output(setup):
    chroma, out = setup
    fake_vecs = np.random.rand(10, 128).tolist()
    fake_metas = [
        {"article_id": str(i), "title": f"文章{i}"}
        for i in range(10)
    ]
    mock_name_result = {
        "name": "AI技术",
        "description": "人工智能相关技术",
        "keywords": ["AI", "深度学习"],
    }
    with (
        patch("src.cluster.VecStore") as MockStore,
        patch("src.cluster.name_cluster", return_value=mock_name_result),
    ):
        mock_instance = MagicMock()
        mock_instance.fetch_with_meta.return_value = (
            [f"id-{i}" for i in range(10)],
            fake_vecs,
            fake_metas,
        )
        MockStore.return_value = mock_instance
        result = run_cluster(chroma_path=chroma, db=Path(":memory:"), out_path=out)

    assert "clusters" in result
    assert result["clusters"][0]["name"] == "AI技术"
    assert "keywords" in result["clusters"][0]
    assert out.exists()


def test_run_cluster_handles_noise(setup):
    chroma, out = setup
    # 所有向量相同 → HDBSCAN 会把它们放一个簇
    fake_vecs = [[0.1] * 128] * 10
    fake_metas = [
        {"article_id": str(i), "title": f"文章{i}"}
        for i in range(10)
    ]
    with (
        patch("src.cluster.VecStore") as MockStore,
        patch("src.cluster.name_cluster", return_value={"name": "测试", "description": "desc", "keywords": []}),
    ):
        mock_instance = MagicMock()
        mock_instance.fetch_with_meta.return_value = (
            [f"id-{i}" for i in range(10)],
            fake_vecs,
            fake_metas,
        )
        MockStore.return_value = mock_instance
        result = run_cluster(chroma_path=chroma, db=Path(":memory:"), out_path=out)

    assert len(result["clusters"]) >= 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/unit/test_cluster.py -v`
Expected: FAIL

- [ ] **Step 3: 重写 `src/cluster.py`**

```python
# src/cluster.py
"""Cluster stage: HDBSCAN/K-means clustering + LLM naming."""

import argparse
import json
import math
import os
from collections import defaultdict
from pathlib import Path

import hdbscan
import numpy as np
from sklearn.cluster import KMeans

from src.lib.db import fetch_all_articles, init_db
from src.lib.llm import name_cluster
from src.lib.vec import VecStore

NOISE_RATIO_THRESHOLD = 0.30


def cluster_vectors(
    vectors: list[list[float]],
    *,
    min_cluster_size: int = 5,
    min_samples: int | None = None,
) -> tuple[list[int], str]:
    arr = np.asarray(vectors, dtype=float)
    h = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric="euclidean",
    )
    labels = h.fit_predict(arr).tolist()
    noise_ratio = sum(1 for l in labels if l == -1) / max(len(labels), 1)
    if (
        noise_ratio <= NOISE_RATIO_THRESHOLD
        and len({l for l in labels if l != -1}) >= 2
    ):
        return labels, "hdbscan"
    k = max(2, round(math.sqrt(len(vectors) / 2)))
    km = KMeans(n_clusters=k, n_init=10, random_state=42)
    return km.fit_predict(arr).tolist(), "kmeans"


def _find_representative(
    vecs: list[list[float]], indices: list[int], cluster_center: list[float]
) -> int:
    """Find the article closest to cluster center."""
    center = np.array(cluster_center)
    best_idx = indices[0]
    best_sim = -1
    for idx in indices:
        v = np.array(vecs[idx])
        sim = float(np.dot(center, v) / (np.linalg.norm(center) * np.linalg.norm(v) + 1e-8))
        if sim > best_sim:
            best_sim = sim
            best_idx = idx
    return best_idx


def run_cluster(
    *,
    chroma_path: Path,
    db: Path,
    out_path: Path,
    min_cluster_size: int = 5,
) -> dict:
    init_db(db)
    store = VecStore(chroma_path)
    ids, vecs, metas = store.fetch_with_meta()

    if not ids:
        return {"method": "none", "clusters": []}

    labels, method = cluster_vectors(vecs, min_cluster_size=min_cluster_size)

    articles_map = {str(a["id"]): a for a in fetch_all_articles(db)}

    by_cluster: dict[int, list[int]] = defaultdict(list)
    for i, label in enumerate(labels):
        if label != -1:
            by_cluster[label].append(i)

    # Compute cluster centers for representative article selection
    arr = np.asarray(vecs, dtype=float)

    clusters = []
    for cid, indices in sorted(by_cluster.items()):
        article_metas = [metas[i] for i in indices]
        titles = [m["title"] for m in article_metas]
        summaries = []
        for m in article_metas:
            aid = m.get("article_id", "")
            art = articles_map.get(aid, {})
            s = art.get("summary", "")
            if s and s != m["title"]:
                summaries.append(s)

        center = arr[indices].mean(axis=0).tolist()
        rep_idx = _find_representative(vecs, indices, center)

        try:
            named = name_cluster(titles)
            name = named["name"]
            desc = named["description"]
        except Exception as e:
            print(f"[cluster] cluster {cid} naming failed: {e}")
            name = titles[0][:12] if titles else f"领域{cid}"
            desc = f"由 {len(titles)} 篇文章自动聚类"

        cluster_keywords = set()
        for m in article_metas:
            aid = m.get("article_id", "")
            art = articles_map.get(aid, {})
            kws = art.get("keywords", "[]")
            try:
                cluster_keywords.update(json.loads(kws))
            except (json.JSONDecodeError, TypeError):
                pass

        top_articles = []
        for i in indices[:3]:
            aid = metas[i].get("article_id", "")
            art = articles_map.get(aid, {})
            top_articles.append({
                "id": int(aid) if aid.isdigit() else aid,
                "title": metas[i]["title"],
                "summary": art.get("summary", ""),
            })

        clusters.append({
            "cluster_id": cid,
            "name": name,
            "description": desc,
            "keywords": sorted(cluster_keywords)[:10],
            "article_ids": [
                int(m["article_id"]) if m["article_id"].isdigit()
                else m["article_id"]
                for m in article_metas
            ],
            "top_articles": top_articles,
        })

    payload = {
        "method": method,
        "clusters": clusters,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chroma", default=os.environ.get("CHROMA_PATH", "data/chroma"))
    ap.add_argument("--db", default=os.environ.get("DB_PATH", "data/articles.db"))
    out = os.environ.get("OUT_DIR", "out")
    ap.add_argument("--out", default=f"{out}/clusters_named.json")
    ap.add_argument("--min-cluster-size", type=int, default=5)
    a = ap.parse_args()

    p = run_cluster(
        chroma_path=Path(a.chroma),
        db=Path(a.db),
        out_path=Path(a.out),
        min_cluster_size=a.min_cluster_size,
    )
    n = len(p["clusters"])
    total = sum(len(c["article_ids"]) for c in p["clusters"])
    print(f"method={p['method']} clusters={n} articles={total}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/unit/test_cluster.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add src/cluster.py tests/unit/test_cluster.py
git commit -m "refactor(cluster): merge naming into cluster stage with richer context"
```

---

### Task 10: 小改 `src/network.py` — 适配新数据格式

**Files:**
- Modify: `src/network.py`

`network.py` 的核心算法不变，只需调整数据格式适配。当前实现已足够通用，只需确保 `fetch_with_meta` 中 `article_id` 类型一致。

- [ ] **Step 1: 确认 network.py 无需修改**

`network.py` 使用 `clusters_named.json`（新格式兼容）和 ChromaDB 向量（不变），代码无需修改。

运行现有测试验证：

Run: `uv run pytest tests/unit/test_network.py -v`
Expected: PASS

- [ ] **Step 2: 提交（如果有改动）**

无需改动则跳过提交。

---

## Phase 4: 展示层（publish + templates）

### Task 11: 重写 Jinja2 模板

**Files:**
- Rewrite: `templates/index.md.j2`
- Rewrite: `templates/domain.md.j2`
- Rewrite: `templates/article.md.j2`
- Rewrite: `templates/network.html.j2`

- [ ] **Step 1: 重写 `templates/article.md.j2`**

```jinja2
{# templates/article.md.j2 #}
# {{ article.title }}

{% if article.url %}[阅读原文]({{ article.url }}){% endif %}

- **来源**：{{ article.feed_name or "未知" }}
- **所属领域**：[{{ cluster.name }}](/domains/{{ cluster.cluster_id }})
- **发布时间**：{{ article.published_at or "未知" }}
{% if article.keywords and article.keywords != "[]" %}

## 关键词

{% for kw in keywords_list %}`{{ kw }}` {% endfor %}
{% endif %}
{% if article.summary and article.summary != article.title %}

## 摘要

{{ article.summary }}
{% endif %}
```

- [ ] **Step 2: 重写 `templates/domain.md.j2`**

```jinja2
{# templates/domain.md.j2 #}
# {{ cluster.name }}

> {{ cluster.description }}

**文章数**：{{ cluster.article_ids|length }}
{% if cluster.keywords %}

## 领域关键词

{% for kw in cluster.keywords %}`{{ kw }}` {% endfor %}
{% endif %}

## 代表性文章

{% for a in top_articles %}
- **{{ a.title }}**{% if a.summary %} — {{ a.summary }}{% endif %}
{% endfor %}

## 全部文章

{% for a in articles %}
- [{{ a.title }}]({% if a.url %}{{ a.url }}{% else %}/articles/{{ a.id }}{% endif %}) {% if a.published_at %}_{{ a.published_at[:10] }}_{% endif %}
{% endfor %}

## 关联领域

{% for r in related %}
- [{{ r.name }}](/domains/{{ r.cluster_id }}) — 相似度 {{ "%.2f" % r.weight }}
{% endfor %}
```

- [ ] **Step 3: 重写 `templates/index.md.j2`**

```jinja2
{# templates/index.md.j2 #}
# 技术文章知识地图

<iframe src="/network.html" width="100%" height="600" frameborder="0"></iframe>

## 桥梁领域

{% for b in bridges %}
- **[{{ b.name }}](/domains/{{ b.cluster_id }})** — betweenness {{ "%.4f" % b.betweenness }}
{% endfor %}

## 所有领域

| 领域 | 文章数 | 描述 |
|------|--------|------|
{% for c in clusters %}| [{{ c.name }}](/domains/{{ c.cluster_id }}) | {{ c.article_ids|length }} | {{ c.description }} |
{% endfor %}

## 最新文章

{% for a in recent_articles %}
- [{{ a.title }}]({% if a.url %}{{ a.url }}{% else %}/articles/{{ a.id }}{% endif %}) — {{ a.feed_name }} — {{ a.published_at[:10] if a.published_at else "" }}
{% endfor %}
```

- [ ] **Step 4: 优化 `templates/network.html.j2` — 增加 hover 提示**

```html
{# templates/network.html.j2 #}
<!doctype html>
<html><head><meta charset="utf-8"><title>领域网络</title>
<style>
body{margin:0;font-family:system-ui}
svg{width:100vw;height:100vh}
.node circle{stroke:#fff;stroke-width:1.5px;cursor:pointer}
.node text{font-size:12px;pointer-events:none}
.bridge circle{stroke:#e63946;stroke-width:3px}
.link{stroke:#999;stroke-opacity:.5}
.tooltip{position:absolute;background:rgba(0,0,0,.8);color:#fff;padding:8px 12px;border-radius:4px;font-size:12px;max-width:280px;pointer-events:none;z-index:10}
</style></head>
<body>
<div class="tooltip" id="tip" style="display:none"></div>
<svg></svg>
<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
const data = {{ data_json | safe }};
const bridgeIds = new Set(data.bridges.map(b => b.cluster_id));
const tip = document.getElementById("tip");
const svg = d3.select("svg"), w = innerWidth, h = innerHeight;
const sim = d3.forceSimulation(data.nodes)
  .force("link", d3.forceLink(data.edges).id(d => d.cluster_id).distance(120))
  .force("charge", d3.forceManyBody().strength(-300))
  .force("center", d3.forceCenter(w/2, h/2));
const link = svg.append("g").attr("class","links").selectAll("line")
  .data(data.edges).enter().append("line").attr("class","link")
  .attr("stroke-width", d => Math.max(1, Math.sqrt(d.weight)));
const node = svg.append("g").selectAll("g").data(data.nodes).enter()
  .append("g").attr("class", d => "node" + (bridgeIds.has(d.cluster_id) ? " bridge" : ""))
  .on("click", (_, d) => location.href = `/domains/${d.cluster_id}`)
  .on("mouseover", (ev, d) => {
    tip.style.display = "block"
       .innerHTML = `<strong>${d.name}</strong><br>${d.size} 篇文章`;
    tip.style.left = (ev.pageX + 12) + "px";
    tip.style.top = (ev.pageY - 30) + "px";
  })
  .on("mouseout", () => { tip.style.display = "none"; });
node.append("circle").attr("r", d => 6 + Math.sqrt(d.size) * 3).attr("fill", "#1f77b4");
node.append("text").attr("dx", 12).attr("dy", "0.35em").text(d => d.name);
sim.on("tick", () => {
  link.attr("x1", d => d.source.x).attr("y1", d => d.source.y)
      .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
  node.attr("transform", d => `translate(${d.x},${d.y})`);
});
</script></body></html>
```

- [ ] **Step 5: 提交**

```bash
git add templates/
git commit -m "refactor(templates): enhanced display with summary, keywords, and tooltips"
```

---

### Task 12: 重写 `src/publish.py` — 适配新数据模型

**Files:**
- Rewrite: `src/publish.py`
- Rewrite: `tests/unit/test_publish.py`

- [ ] **Step 1: 写失败测试**

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/unit/test_publish.py -v`
Expected: FAIL

- [ ] **Step 3: 重写 `src/publish.py`**

```python
# src/publish.py
"""Render VitePress site from pipeline outputs."""

import argparse
import json
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.lib.db import fetch_all_articles, init_db


def _env(templates_dir: str | Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html"]),
        keep_trailing_newline=True,
    )


def _related(
    cluster_id: int,
    edges: list[dict],
    names: dict[int, str],
    k: int = 5,
) -> list[dict]:
    rels: list[tuple[int, float]] = []
    for e in edges:
        if e["source"] == cluster_id:
            rels.append((e["target"], e["weight"]))
        elif e["target"] == cluster_id:
            rels.append((e["source"], e["weight"]))
    rels.sort(key=lambda x: x[1], reverse=True)
    return [
        {"cluster_id": cid, "name": names.get(cid, str(cid)), "weight": w}
        for cid, w in rels[:k]
    ]


def render_site(
    *,
    named_path: Path,
    network_path: Path,
    db: Path,
    templates_dir: str | Path,
    site_dir: Path,
) -> None:
    init_db(db)
    named = json.loads(Path(named_path).read_text())
    network = json.loads(Path(network_path).read_text())
    articles = {str(a["id"]): a for a in fetch_all_articles(db)}
    name_by_cid = {c["cluster_id"]: c["name"] for c in named["clusters"]}

    bridges_full = [
        {
            "cluster_id": b["cluster_id"],
            "name": name_by_cid.get(b["cluster_id"], ""),
            "betweenness": b["betweenness"],
        }
        for b in network["bridges"]
    ]

    # Recent articles sorted by published_at desc
    all_articles_sorted = sorted(
        articles.values(),
        key=lambda a: a.get("published_at") or "",
        reverse=True,
    )
    recent = all_articles_sorted[:20]

    env = _env(templates_dir)
    site_dir = Path(site_dir)
    (site_dir / "domains").mkdir(parents=True, exist_ok=True)
    (site_dir / "articles").mkdir(parents=True, exist_ok=True)

    (site_dir / "index.md").write_text(
        env.get_template("index.md.j2").render(
            clusters=named["clusters"],
            bridges=bridges_full,
            recent_articles=recent,
        ),
        encoding="utf-8",
    )

    network_html = env.get_template("network.html.j2").render(
        data_json=json.dumps(network, ensure_ascii=False)
    )
    (site_dir / "network.html").write_text(network_html, encoding="utf-8")
    (site_dir / "public").mkdir(parents=True, exist_ok=True)
    (site_dir / "public" / "network.html").write_text(network_html, encoding="utf-8")

    for c in named["clusters"]:
        cluster_articles = [
            articles[aid] for aid in (str(a) for a in c["article_ids"])
            if aid in articles
        ]
        page = env.get_template("domain.md.j2").render(
            cluster=c,
            articles=cluster_articles,
            top_articles=c.get("top_articles", []),
            related=_related(c["cluster_id"], network["edges"], name_by_cid),
        )
        (site_dir / "domains" / f"{c['cluster_id']}.md").write_text(
            page, encoding="utf-8",
        )

        for aid in c["article_ids"]:
            aid_str = str(aid)
            if aid_str not in articles:
                continue
            art = articles[aid_str]
            keywords_list = []
            try:
                keywords_list = json.loads(art.get("keywords", "[]"))
            except (json.JSONDecodeError, TypeError):
                pass
            (site_dir / "articles" / f"{aid}.md").write_text(
                env.get_template("article.md.j2").render(
                    article=art, cluster=c, keywords_list=keywords_list,
                ),
                encoding="utf-8",
            )


def main() -> None:
    ap = argparse.ArgumentParser()
    out = os.environ.get("OUT_DIR", "out")
    ap.add_argument("--named", default=f"{out}/clusters_named.json")
    ap.add_argument("--network", default=f"{out}/network.json")
    ap.add_argument("--db", default=os.environ.get("DB_PATH", "data/articles.db"))
    ap.add_argument("--templates", default="templates")
    ap.add_argument("--site", default=os.environ.get("SITE_DIR", "site/docs"))
    a = ap.parse_args()
    render_site(
        named_path=Path(a.named),
        network_path=Path(a.network),
        db=Path(a.db),
        templates_dir=a.templates,
        site_dir=Path(a.site),
    )
    print(f"published to {a.site}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/unit/test_publish.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/publish.py tests/unit/test_publish.py
git commit -m "refactor(publish): adapt to new data model with summary and keywords"
```

---

## Phase 5: 集成与清理

### Task 13: 更新 `Makefile` + `pyproject.toml`

**Files:**
- Modify: `Makefile`
- Modify: `pyproject.toml`

- [ ] **Step 1: 更新 `Makefile`**

```makefile
.PHONY: ingest refresh build serve all test clean
SHELL := /bin/bash
PY := uv run python

WEMP_DB ?= /Users/wqw/Documents/idea_work/tools/we-mp-rss/data/we_mp_rss.db

ingest:
	$(PY) -m src.ingest --wemp $(WEMP_DB)

refresh:
	$(PY) -m src.ingest --wemp $(WEMP_DB)
	$(PY) -m src.clean
	$(PY) -m src.summarize
	$(PY) -m src.embed
	$(PY) -m src.cluster
	$(PY) -m src.network
	$(PY) -m src.publish

build:
	cd site && pnpm install && pnpm build

serve:
	cd site && pnpm dev

all: refresh build

test:
	uv run pytest

clean:
	rm -rf out data/articles.db data/chroma site/.vitepress/dist site/.vitepress/cache
```

- [ ] **Step 2: 更新 `pyproject.toml`**

新增 `beautifulsoup4` 和 `lxml`，移除 `jieba`：

```toml
dependencies = [
    "ollama>=0.3.0",
    "openai>=1.50.0",
    "chromadb>=0.5.0",
    "hdbscan>=0.8.38",
    "scikit-learn>=1.5.0",
    "networkx>=3.3",
    "beautifulsoup4>=4.12.0",
    "lxml>=5.0.0",
    "jinja2>=3.1.4",
    "python-dotenv>=1.0.1",
    "tenacity>=8.5.0",
]
```

- [ ] **Step 3: 安装依赖并验证**

Run: `http_proxy=http://127.0.0.1:7897 https_proxy=http://127.0.0.1:7897 uv sync`
Expected: 依赖安装成功

- [ ] **Step 4: 提交**

```bash
git add Makefile pyproject.toml uv.lock
git commit -m "refactor: update Makefile for V2 pipeline and swap jieba for beautifulsoup4"
```

---

### Task 14: 删除旧文件

**Files:**
- Delete: `src/name.py`
- Delete: `src/lib/parse.py`
- Delete: `src/lib/tfidf_fallback.py`
- Delete: `scripts/migrate_markdown.py`
- Delete: `tests/unit/test_parse.py`
- Delete: `tests/unit/test_tfidf_fallback.py`
- Delete: `tests/integration/test_migrate.py`
- Delete: `tests/integration/test_name.py`
- Delete: `tests/integration/test_regression.py`（snapshot 基于 53 篇旧数据，需重建）

- [ ] **Step 1: 删除旧文件**

```bash
rm src/name.py src/lib/parse.py src/lib/tfidf_fallback.py scripts/migrate_markdown.py
rm tests/unit/test_parse.py tests/unit/test_tfidf_fallback.py
rm tests/integration/test_migrate.py tests/integration/test_name.py tests/integration/test_regression.py
```

- [ ] **Step 2: 验证测试仍可运行**

Run: `uv run pytest tests/unit/ -v --no-header -q`
Expected: 仅运行新测试，旧测试已删除

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "chore: remove obsolete V1 files (name, parse, tfidf, migrate)"
```

---

### Task 15: 端到端集成测试

**Files:**
- Rewrite: `tests/integration/test_pipeline_e2e.py`

- [ ] **Step 1: 写端到端测试（mock LLM/embedding）**

```python
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
            CREATE TABLE feeds (id TEXT PRIMARY KEY, name TEXT);
            CREATE TABLE articles (
                id TEXT PRIMARY KEY, feed_id TEXT, title TEXT,
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
    """Run all stages: ingest → clean → summarize → embed → cluster → network → publish."""
    fake_vecs = [np.random.rand(128).tolist() for _ in range(20)]
    fake_name = {"name": "测试领域", "description": "自动测试", "keywords": ["测试"]}
    fake_summary = {"summary": f"文章摘要", "keywords": ["技术"]}

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
        from src.publish import render_site

        # Stage 1: ingest
        n = run_ingest(wemp=paths["wemp"], db=paths["db"])
        assert n == 20

        # Stage 2: clean
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
        render_site(
            named_path=out_path, network_path=net_path, db=paths["db"],
            templates_dir="templates", site_dir=paths["site"],
        )
        assert (paths["site"] / "index.md").exists()
        assert (paths["site"] / "network.html").exists()
```

- [ ] **Step 2: 运行端到端测试**

Run: `uv run pytest tests/integration/test_pipeline_e2e.py -v`
Expected: PASS

- [ ] **Step 3: 提交**

```bash
git add tests/integration/test_pipeline_e2e.py
git commit -m "test(e2e): rewrite pipeline E2E test for V2 stages"
```

---

### Task 16: 真实数据验证

**Files:** 无新文件

- [ ] **Step 1: 清理旧数据**

Run: `make clean`

- [ ] **Step 2: 运行完整 pipeline**

Run: `make refresh`

- [ ] **Step 3: 检查输出**

Run:
```bash
# 检查导入数量
sqlite3 data/articles.db "SELECT COUNT(*), has_fulltext FROM articles GROUP BY has_fulltext;"
# 检查各阶段完成数量
sqlite3 data/articles.db "SELECT pipeline_stage, COUNT(*) FROM articles GROUP BY pipeline_stage;"
# 检查聚类结果
cat out/clusters_named.json | python -m json.tool | head -30
```

Expected:
- 导入 ~437 篇文章
- ~114 篇 has_fulltext=1
- 聚类有多个有意义的领域

- [ ] **Step 4: 本地预览**

Run: `make serve`
打开浏览器查看 VitePress 站点效果

- [ ] **Step 5: 确认后提交**

```bash
git add -A
git commit -m "feat: V2 pipeline running with We-MP-RSS data"
```

---

## 自检结果

**1. Spec 覆盖度**：
- [x] 新数据模型 → Task 1
- [x] ingest from We-MP-RSS → Task 2
- [x] HTML 清洗 → Task 3, 4
- [x] LLM 摘要 → Task 5, 6
- [x] title+summary 嵌入 → Task 7
- [x] 聚类+命名合并 → Task 9
- [x] 网络分析 → Task 10（无需修改）
- [x] 增强发布 → Task 11, 12
- [x] Makefile → Task 13
- [x] 旧文件清理 → Task 14
- [x] 测试 → Task 15, 16

**2. Placeholder 扫描**：无 TBD/TODO/模糊描述

**3. 类型一致性**：所有函数签名、字段名在上下游 task 中一致（source_id, feed_id, feed_name, pipeline_stage 等）
