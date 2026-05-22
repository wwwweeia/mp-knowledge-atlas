# 技术文章知识地图 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 53 篇技术文章自动聚类成"领域"，识别桥梁领域，发布为可交互的 VitePress 知识地图站。

**Architecture:** Makefile 串联 6 个独立 stage（ingest → embed → cluster → name → network → publish），SQLite 是单一真理源，ChromaDB 是向量缓存，所有中间产物落 JSON。无常驻服务、无 Web 后端。

**Tech Stack:** Python 3.12 + uv，SQLite，ChromaDB，OpenAI `text-embedding-3-small`，HDBSCAN/K-means，networkx，Claude Haiku 4.5 (`claude-haiku-4-5-20251001`)，jieba（fallback），VitePress + D3，Jinja2 模板，pytest。

**Spec：** [`docs/superpowers/specs/2026-05-21-knowledge-map-mvp-design.md`](../specs/2026-05-21-knowledge-map-mvp-design.md)

---

## 文件结构总览

```
pyproject.toml                  # uv + 依赖
.env.example                    # OPENAI_API_KEY / ANTHROPIC_API_KEY
.gitignore                      # out/ data/ site/.vitepress/dist/ 等
Makefile                        # migrate / refresh / build / serve / all / test

src/
├── lib/
│   ├── db.py                   # SQLite 连接 + schema + 通用查询
│   ├── parse.py                # Markdown 索引解析（纯函数）
│   ├── embedding.py            # OpenAI embedding 客户端（指数退避）
│   ├── vec.py                  # ChromaDB 客户端封装
│   ├── llm.py                  # Claude Haiku 调用（含重试）
│   └── tfidf_fallback.py       # jieba 分词 + TF-IDF 关键词
├── embed.py                    # SQLite → OpenAI embedding → ChromaDB
├── cluster.py                  # ChromaDB → HDBSCAN / K-means → out/clusters.json
├── name.py                     # clusters.json → Haiku 命名 → out/clusters_named.json
├── network.py                  # clusters_named → networkx → out/network.json
└── publish.py                  # 三个 JSON + SQLite → site/docs/ markdown

scripts/
└── migrate_markdown.py         # 一次性：articles/*.md → SQLite

templates/                      # Jinja2 模板
├── index.md.j2
├── domain.md.j2
├── article.md.j2
└── network.html.j2

tests/
├── unit/                       # test_parse / test_db / test_cluster / test_network /
│   └── ...                     # test_publish / test_tfidf_fallback / test_embedding / test_vec / test_llm
├── integration/                # test_migrate / test_embed / test_name /
│   └── ...                     # test_pipeline_e2e / test_regression
└── fixtures/
    ├── mini_index.md
    └── regression_snapshot.json

site/                           # VitePress（package.json + .vitepress/config.ts）
data/                           # SQLite + ChromaDB 持久化（gitignore）
out/                            # pipeline 中间产物（gitignore）
```

---

## Phase 0 — 项目初始化（约 0.5 天）

### Task 1: pyproject + 环境基础

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.gitignore`

- [ ] **Step 1: 写 pyproject.toml**

```toml
[project]
name = "tech-articles-collector"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "openai>=1.40.0",
    "anthropic>=0.40.0",
    "chromadb>=0.5.0",
    "hdbscan>=0.8.38",
    "scikit-learn>=1.5.0",
    "networkx>=3.3",
    "jieba>=0.42.1",
    "jinja2>=3.1.4",
    "python-dotenv>=1.0.1",
    "tenacity>=8.5.0",
]

[dependency-groups]
dev = ["pytest>=8.3.0", "pytest-cov>=5.0.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-v --cov=src --cov-report=term-missing"
```

- [ ] **Step 2: 写 .env.example**

```
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
DB_PATH=data/articles.db
CHROMA_PATH=data/chroma
OUT_DIR=out
SITE_DIR=site/docs
```

- [ ] **Step 3: 写 .gitignore**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.coverage
data/
out/
site/node_modules/
site/.vitepress/cache/
site/.vitepress/dist/
.env
```

- [ ] **Step 4: 验证 uv sync 通过**

Run: `http_proxy=http://127.0.0.1:7897 https_proxy=http://127.0.0.1:7897 all_proxy=socks5://127.0.0.1:7897 uv sync`
Expected: 所有依赖安装成功，无解析错误。

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .env.example .gitignore
git commit -m "chore: 初始化 Python 项目结构与依赖"
```

---

## Phase 1 — 数据基线（2-3 天）

### Task 2: lib/db.py — SQLite 连接 + schema

**Files:**
- Create: `src/__init__.py`、`src/lib/__init__.py`
- Create: `src/lib/db.py`
- Create: `tests/__init__.py`、`tests/unit/__init__.py`、`tests/unit/test_db.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_db.py
import sqlite3
from src.lib.db import init_db, get_conn, insert_article, fetch_pending_embeddings

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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/unit/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.lib.db'`

- [ ] **Step 3: 写最小实现**

```python
# src/lib/db.py
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id           INTEGER PRIMARY KEY,
    title        TEXT NOT NULL,
    url          TEXT,
    source       TEXT,
    source_name  TEXT,
    manual_tag   TEXT,
    summary      TEXT,
    added_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    embedding_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_embedding ON articles(embedding_id);
"""

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
    finally:
        c.close()

def insert_article(conn, *, title, url, source, source_name, manual_tag, summary):
    conn.execute(
        "INSERT INTO articles (title, url, source, source_name, manual_tag, summary) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (title, url, source, source_name, manual_tag, summary),
    )

def fetch_pending_embeddings(path: Path):
    with get_conn(path) as c:
        rows = c.execute(
            "SELECT id, title, summary FROM articles "
            "WHERE embedding_id IS NULL OR embedding_id = '__failed__'"
        ).fetchall()
    return [dict(r) for r in rows]

def mark_embedded(path: Path, article_id: int, embedding_id: str) -> None:
    with get_conn(path) as c:
        c.execute("UPDATE articles SET embedding_id=? WHERE id=?",
                  (embedding_id, article_id))

def fetch_all_articles(path: Path):
    with get_conn(path) as c:
        rows = c.execute("SELECT * FROM articles").fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/unit/test_db.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/lib/db.py src/__init__.py src/lib/__init__.py tests/
git commit -m "feat(db): 添加 SQLite 连接、schema 初始化与文章 CRUD"
```

---

### Task 3: lib/parse.py — Markdown 索引解析

**Files:**
- Create: `src/lib/parse.py`
- Create: `tests/unit/test_parse.py`
- Create: `tests/fixtures/mini_index.md`

- [ ] **Step 1: 写 fixture 与失败测试**

```markdown
<!-- tests/fixtures/mini_index.md -->
### AI Coding / Claude Code

| # | 标题 | 链接 | 来源 | 收藏日期 |
|---|------|------|------|---------|
| 1 | Claude Code 实战 | [微信](https://mp.weixin.qq.com/s/a) | mp公众号 | 2026-01-10 |
| 2 | Cursor vs Claude | 未找到 | 未知 | 2026-01-12 |

### Agent 架构 / Skills

| # | 标题 | 链接 | 来源 | 收藏日期 |
|---|------|------|------|---------|
| 3 | Skills 设计 | [转载(知乎)](https://zhuanlan.zhihu.com/p/1) | 知乎 | 2026-02-01 |
```

```python
# tests/unit/test_parse.py
from pathlib import Path
from src.lib.parse import parse_index

FIXTURE = Path("tests/fixtures/mini_index.md")

def test_parse_extracts_three_rows():
    rows = parse_index(FIXTURE.read_text())
    assert len(rows) == 3

def test_parse_assigns_manual_tag_from_section():
    rows = parse_index(FIXTURE.read_text())
    assert rows[0]["manual_tag"] == "AI Coding / Claude Code"
    assert rows[2]["manual_tag"] == "Agent 架构 / Skills"

def test_parse_url_and_source():
    rows = parse_index(FIXTURE.read_text())
    assert rows[0]["url"] == "https://mp.weixin.qq.com/s/a"
    assert rows[0]["source"] == "wechat"
    assert rows[1]["url"] is None
    assert rows[1]["source"] is None
    assert rows[2]["source"] == "zhihu"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/unit/test_parse.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 写实现**

```python
# src/lib/parse.py
import re

ROW_RE = re.compile(r"^\|\s*\d+\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|$")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
SECTION_RE = re.compile(r"^###\s+(.+?)\s*$")

SOURCE_BY_DOMAIN = {
    "mp.weixin.qq.com": "wechat",
    "zhuanlan.zhihu.com": "zhihu",
    "zhihu.com": "zhihu",
    "blog.csdn.net": "csdn",
    "developer.aliyun.com": "aliyun",
}

def _source_from_url(url: str | None) -> str | None:
    if not url:
        return None
    for dom, src in SOURCE_BY_DOMAIN.items():
        if dom in url:
            return src
    return "other"

def parse_index(text: str) -> list[dict]:
    rows = []
    section = None
    for line in text.splitlines():
        m_sec = SECTION_RE.match(line)
        if m_sec:
            section = m_sec.group(1).strip()
            continue
        if line.startswith("|---") or "标题" in line:
            continue
        m = ROW_RE.match(line)
        if not m:
            continue
        title, link_cell, _src_cell, _date = (s.strip() for s in m.groups())
        link_m = LINK_RE.search(link_cell)
        url = link_m.group(2) if link_m else None
        if url and not url.startswith("http"):
            url = None
        rows.append({
            "title": title,
            "url": url,
            "source": _source_from_url(url),
            "manual_tag": section,
        })
    return rows
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/unit/test_parse.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/lib/parse.py tests/unit/test_parse.py tests/fixtures/mini_index.md
git commit -m "feat(parse): 解析 Markdown 索引为带 manual_tag 的文章列表"
```

---

### Task 4: scripts/migrate_markdown.py — 一次性迁移

**Files:**
- Create: `scripts/__init__.py`、`scripts/migrate_markdown.py`
- Create: `tests/integration/__init__.py`、`tests/integration/test_migrate.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/integration/test_migrate.py
import sqlite3
import subprocess

def test_migrate_writes_articles_to_sqlite(tmp_path):
    idx = tmp_path / "ai.md"
    idx.write_text(
        "### AI Coding\n\n"
        "| # | 标题 | 链接 | 来源 | 收藏日期 |\n"
        "|---|------|------|------|---------|\n"
        "| 1 | 测试文章 | [微信](https://mp.weixin.qq.com/s/x) | mp公众号 | 2026-05-01 |\n"
    )
    db = tmp_path / "t.db"
    r = subprocess.run(
        ["uv", "run", "python", "-m", "scripts.migrate_markdown",
         "--dir", str(tmp_path), "--db", str(db)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    rows = sqlite3.connect(db).execute(
        "SELECT title, url, manual_tag FROM articles"
    ).fetchall()
    assert rows == [("测试文章", "https://mp.weixin.qq.com/s/x", "AI Coding")]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/integration/test_migrate.py -v`
Expected: FAIL — `No module named scripts.migrate_markdown`

- [ ] **Step 3: 写实现**

```python
# scripts/migrate_markdown.py
import argparse
from pathlib import Path
from src.lib.db import init_db, get_conn, insert_article
from src.lib.parse import parse_index

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="包含 *.md 索引的目录")
    ap.add_argument("--db", required=True)
    args = ap.parse_args()

    db = Path(args.db)
    init_db(db)
    total = 0
    for md in sorted(Path(args.dir).glob("*.md")):
        if md.name == "index.md":
            continue
        rows = parse_index(md.read_text())
        with get_conn(db) as c:
            for r in rows:
                insert_article(c, title=r["title"], url=r["url"], source=r["source"],
                               source_name=None, manual_tag=r["manual_tag"], summary=None)
        total += len(rows)
    print(f"inserted={total}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/integration/test_migrate.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/ tests/integration/__init__.py tests/integration/test_migrate.py
git commit -m "feat(migrate): 一次性把 articles/*.md 迁移到 SQLite"
```

---

### Task 5: lib/embedding.py — OpenAI client with retry

**Files:**
- Create: `src/lib/embedding.py`
- Create: `tests/unit/test_embedding.py`

- [ ] **Step 1: 写失败测试（mock OpenAI）**

```python
# tests/unit/test_embedding.py
from unittest.mock import MagicMock
from src.lib.embedding import embed_texts

def test_embed_texts_calls_openai_and_returns_vectors():
    fake = MagicMock()
    fake.embeddings.create.return_value = MagicMock(
        data=[MagicMock(embedding=[0.1, 0.2]),
              MagicMock(embedding=[0.3, 0.4])]
    )
    vecs = embed_texts(["a", "b"], client=fake)
    assert vecs == [[0.1, 0.2], [0.3, 0.4]]
    fake.embeddings.create.assert_called_once_with(
        model="text-embedding-3-small", input=["a", "b"]
    )

def test_embed_texts_retries_on_transient_error():
    from openai import APIConnectionError
    fake = MagicMock()
    fake.embeddings.create.side_effect = [
        APIConnectionError(request=MagicMock()),
        MagicMock(data=[MagicMock(embedding=[1.0])]),
    ]
    vecs = embed_texts(["x"], client=fake)
    assert vecs == [[1.0]]
    assert fake.embeddings.create.call_count == 2
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/unit/test_embedding.py -v`
Expected: FAIL — `No module named src.lib.embedding`

- [ ] **Step 3: 写实现**

```python
# src/lib/embedding.py
import os
from openai import OpenAI, APIConnectionError, RateLimitError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

MODEL = "text-embedding-3-small"

def get_client() -> OpenAI:
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((APIConnectionError, RateLimitError)),
    reraise=True,
)
def embed_texts(texts: list[str], *, client: OpenAI | None = None) -> list[list[float]]:
    cli = client or get_client()
    resp = cli.embeddings.create(model=MODEL, input=texts)
    return [d.embedding for d in resp.data]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/unit/test_embedding.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/lib/embedding.py tests/unit/test_embedding.py
git commit -m "feat(embedding): 封装 OpenAI embedding 调用与指数退避重试"
```

---

### Task 6: lib/vec.py — ChromaDB 封装

**Files:**
- Create: `src/lib/vec.py`
- Create: `tests/unit/test_vec.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_vec.py
from src.lib.vec import VecStore

def test_add_and_fetch(tmp_path):
    store = VecStore(tmp_path / "chroma")
    store.add(ids=["a", "b"], embeddings=[[1.0, 0.0], [0.0, 1.0]],
              metadatas=[{"article_id": 1, "title": "A"},
                         {"article_id": 2, "title": "B"}])
    ids, vecs = store.fetch_all()
    assert set(ids) == {"a", "b"}
    assert len(vecs) == 2 and len(vecs[0]) == 2

def test_persistence(tmp_path):
    p = tmp_path / "chroma"
    VecStore(p).add(ids=["a"], embeddings=[[1.0]], metadatas=[{"article_id": 1}])
    ids, _ = VecStore(p).fetch_all()
    assert ids == ["a"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/unit/test_vec.py -v`
Expected: FAIL — `No module named src.lib.vec`

- [ ] **Step 3: 写实现**

```python
# src/lib/vec.py
from pathlib import Path
import chromadb

COLLECTION = "articles_v1"

class VecStore:
    def __init__(self, path: Path):
        Path(path).mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(path))
        self.col = self.client.get_or_create_collection(COLLECTION)

    def add(self, *, ids: list[str], embeddings: list[list[float]],
            metadatas: list[dict]) -> None:
        self.col.add(ids=ids, embeddings=embeddings, metadatas=metadatas)

    def fetch_all(self) -> tuple[list[str], list[list[float]]]:
        res = self.col.get(include=["embeddings"])
        return res["ids"], [list(v) for v in res["embeddings"]]

    def fetch_with_meta(self):
        res = self.col.get(include=["embeddings", "metadatas"])
        return res["ids"], [list(v) for v in res["embeddings"]], res["metadatas"]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/unit/test_vec.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/lib/vec.py tests/unit/test_vec.py
git commit -m "feat(vec): 封装 ChromaDB 持久化向量存储"
```

---

### Task 7: src/embed.py — 数据库 → 向量库 增量同步

**Files:**
- Create: `src/embed.py`
- Create: `tests/integration/test_embed.py`

- [ ] **Step 1: 写失败测试（mock embedding）**

```python
# tests/integration/test_embed.py
import sqlite3
from unittest.mock import patch
from src.lib.db import init_db, get_conn, insert_article
from src.embed import run_embed

def test_run_embed_marks_articles_and_writes_chroma(tmp_path):
    db = tmp_path / "t.db"
    init_db(db)
    with get_conn(db) as c:
        for i in range(3):
            insert_article(c, title=f"t{i}", url=None, source=None,
                           source_name=None, manual_tag="ai", summary=None)

    with patch("src.embed.embed_texts", return_value=[[0.1, 0.2]] * 3):
        n = run_embed(db=db, chroma_path=tmp_path / "chroma", batch_size=10)

    assert n == 3
    pending = sqlite3.connect(db).execute(
        "SELECT COUNT(*) FROM articles "
        "WHERE embedding_id IS NULL OR embedding_id='__failed__'"
    ).fetchone()[0]
    assert pending == 0
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/integration/test_embed.py -v`
Expected: FAIL — `No module named src.embed`

- [ ] **Step 3: 写实现**

```python
# src/embed.py
import argparse
import os
import uuid
from pathlib import Path
from dotenv import load_dotenv
from src.lib.db import fetch_pending_embeddings, mark_embedded
from src.lib.embedding import embed_texts
from src.lib.vec import VecStore

def _text_for(row: dict) -> str:
    return row["title"] + ("\n\n" + row["summary"] if row.get("summary") else "")

def run_embed(*, db: Path, chroma_path: Path, batch_size: int = 32) -> int:
    pending = fetch_pending_embeddings(db)
    if not pending:
        return 0
    store = VecStore(chroma_path)
    done = 0
    for i in range(0, len(pending), batch_size):
        batch = pending[i:i + batch_size]
        texts = [_text_for(r) for r in batch]
        try:
            vecs = embed_texts(texts)
        except Exception as e:
            print(f"[embed] batch failed: {e}; marking __failed__")
            for r in batch:
                mark_embedded(db, r["id"], "__failed__")
            continue
        ids = [uuid.uuid4().hex for _ in batch]
        metas = [{"article_id": r["id"], "title": r["title"]} for r in batch]
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

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/integration/test_embed.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add src/embed.py tests/integration/test_embed.py
git commit -m "feat(embed): SQLite 待嵌入文章增量写入 ChromaDB"
```

---

## Phase 2 — 聚类 + 命名 + 桥梁（2-3 天）

### Task 8: src/cluster.py — HDBSCAN + K-means fallback

**Files:**
- Create: `src/cluster.py`
- Create: `tests/unit/test_cluster.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_cluster.py
import numpy as np
from src.cluster import cluster_vectors

def _two_blobs(n=12, dim=4, seed=0):
    rng = np.random.default_rng(seed)
    a = rng.normal(loc=0.0, scale=0.05, size=(n, dim))
    b = rng.normal(loc=5.0, scale=0.05, size=(n, dim))
    return np.vstack([a, b]).tolist()

def test_hdbscan_finds_two_clusters_on_clean_blobs():
    vecs = _two_blobs()
    labels, method = cluster_vectors(vecs, min_cluster_size=3)
    distinct = {l for l in labels if l != -1}
    assert len(distinct) == 2
    assert method == "hdbscan"

def test_kmeans_fallback_triggers_when_too_noisy():
    rng = np.random.default_rng(1)
    vecs = rng.normal(size=(20, 4)).tolist()
    labels, method = cluster_vectors(vecs, min_cluster_size=5)
    assert method == "kmeans"
    assert -1 not in labels
    assert len(set(labels)) >= 2
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/unit/test_cluster.py -v`
Expected: FAIL

- [ ] **Step 3: 写实现**

```python
# src/cluster.py
import argparse
import json
import math
import os
from pathlib import Path
import numpy as np
import hdbscan
from sklearn.cluster import KMeans
from src.lib.vec import VecStore

NOISE_RATIO_THRESHOLD = 0.30

def cluster_vectors(vectors: list[list[float]], *, min_cluster_size: int = 3,
                    min_samples: int | None = None) -> tuple[list[int], str]:
    arr = np.asarray(vectors, dtype=float)
    h = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size,
                        min_samples=min_samples, metric="euclidean")
    labels = h.fit_predict(arr).tolist()
    noise_ratio = sum(1 for l in labels if l == -1) / max(len(labels), 1)
    if noise_ratio <= NOISE_RATIO_THRESHOLD and len({l for l in labels if l != -1}) >= 2:
        return labels, "hdbscan"
    k = max(2, round(math.sqrt(len(vectors) / 2)))
    km = KMeans(n_clusters=k, n_init=10, random_state=42)
    return km.fit_predict(arr).tolist(), "kmeans"

def run_cluster(*, chroma_path: Path, out_path: Path, min_cluster_size: int = 3):
    store = VecStore(chroma_path)
    ids, vecs, metas = store.fetch_with_meta()
    labels, method = cluster_vectors(vecs, min_cluster_size=min_cluster_size)
    payload = {
        "method": method,
        "items": [
            {"embedding_id": ids[i], "article_id": metas[i]["article_id"],
             "title": metas[i]["title"], "cluster_id": int(labels[i])}
            for i in range(len(ids))
        ],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chroma", default=os.environ.get("CHROMA_PATH", "data/chroma"))
    ap.add_argument("--out", default=os.environ.get("OUT_DIR", "out") + "/clusters.json")
    ap.add_argument("--min-cluster-size", type=int, default=3)
    a = ap.parse_args()
    p = run_cluster(chroma_path=Path(a.chroma), out_path=Path(a.out),
                    min_cluster_size=a.min_cluster_size)
    n_clusters = len({i["cluster_id"] for i in p["items"] if i["cluster_id"] != -1})
    print(f"method={p['method']} clusters={n_clusters} items={len(p['items'])}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/unit/test_cluster.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/cluster.py tests/unit/test_cluster.py
git commit -m "feat(cluster): HDBSCAN 聚类与高噪音 K-means 兜底"
```

---

### Task 9: lib/tfidf_fallback.py — jieba 关键词兜底

**Files:**
- Create: `src/lib/tfidf_fallback.py`
- Create: `tests/unit/test_tfidf_fallback.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_tfidf_fallback.py
from src.lib.tfidf_fallback import keyword_name

def test_keyword_name_picks_top_terms():
    titles = [
        "Claude Code 实战入门",
        "Claude Code 工作流自动化",
        "Claude Code 与 Cursor 对比",
    ]
    name = keyword_name(titles, top_k=2)
    assert "Claude" in name and "Code" in name

def test_keyword_name_returns_nonempty_for_few_titles():
    assert keyword_name(["Agent 架构"], top_k=2)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/unit/test_tfidf_fallback.py -v`
Expected: FAIL

- [ ] **Step 3: 写实现**

```python
# src/lib/tfidf_fallback.py
import jieba.analyse

STOP = {"的", "了", "是", "在", "和", "与", "或", "及"}

def keyword_name(titles: list[str], *, top_k: int = 3) -> str:
    text = "\n".join(titles)
    words = jieba.analyse.extract_tags(text, topK=top_k * 3,
                                       allowPOS=("n", "nz", "vn", "eng"))
    cleaned = [w for w in words if w not in STOP and len(w) > 1]
    if not cleaned:
        cleaned = [t.strip() for t in titles if t.strip()][:top_k]
    return " / ".join(cleaned[:top_k]) or "未命名"
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/unit/test_tfidf_fallback.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/lib/tfidf_fallback.py tests/unit/test_tfidf_fallback.py
git commit -m "feat(tfidf): jieba TF-IDF 命名兜底"
```

---

### Task 10: lib/llm.py — Claude Haiku 调用

**Files:**
- Create: `src/lib/llm.py`
- Create: `tests/unit/test_llm.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_llm.py
import json
from unittest.mock import MagicMock
from src.lib.llm import name_cluster

def test_name_cluster_returns_parsed_json():
    fake = MagicMock()
    fake.messages.create.return_value = MagicMock(
        content=[MagicMock(text=json.dumps(
            {"name": "AI Coding", "description": "AI 辅助编程相关讨论"},
            ensure_ascii=False))]
    )
    r = name_cluster(["Claude Code 实战", "Cursor 用法"], client=fake)
    assert r == {"name": "AI Coding", "description": "AI 辅助编程相关讨论"}

def test_name_cluster_raises_on_bad_json():
    fake = MagicMock()
    fake.messages.create.return_value = MagicMock(content=[MagicMock(text="not json")])
    try:
        name_cluster(["x"], client=fake)
    except ValueError:
        return
    assert False, "expected ValueError"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/unit/test_llm.py -v`
Expected: FAIL

- [ ] **Step 3: 写实现**

```python
# src/lib/llm.py
import json
import os
from anthropic import Anthropic, APIConnectionError, RateLimitError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

MODEL = "claude-haiku-4-5-20251001"

PROMPT = """你是技术内容编辑。下面是一组属于同一聚类的文章标题，请用中文给这个聚类起一个 6-12 字的领域名称，并写一句不超过 40 字的领域描述。

只输出 JSON：{{"name": "<领域名>", "description": "<一句话描述>"}}

标题列表：
{titles}"""

def get_client() -> Anthropic:
    return Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    retry=retry_if_exception_type((APIConnectionError, RateLimitError)),
    reraise=True,
)
def name_cluster(titles: list[str], *, client: Anthropic | None = None) -> dict:
    cli = client or get_client()
    prompt = PROMPT.format(titles="\n".join(f"- {t}" for t in titles[:20]))
    resp = cli.messages.create(
        model=MODEL, max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return JSON: {text!r}") from e
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/unit/test_llm.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/lib/llm.py tests/unit/test_llm.py
git commit -m "feat(llm): Claude Haiku 聚类命名调用与重试"
```

---

### Task 11: src/name.py — 命名 stage（LLM + fallback）

**Files:**
- Create: `src/name.py`
- Create: `tests/integration/test_name.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/integration/test_name.py
import json
from unittest.mock import patch
from src.name import run_name

def test_run_name_falls_back_to_tfidf_on_llm_failure(tmp_path):
    clusters = {
        "method": "hdbscan",
        "items": [
            {"article_id": 1, "title": "Claude Code 实战", "cluster_id": 0},
            {"article_id": 2, "title": "Claude Code 工作流", "cluster_id": 0},
            {"article_id": 3, "title": "Claude Code 与 Cursor", "cluster_id": 0},
        ],
    }
    src = tmp_path / "clusters.json"
    src.write_text(json.dumps(clusters, ensure_ascii=False))
    out = tmp_path / "named.json"
    with patch("src.name.name_cluster", side_effect=ValueError("bad json")):
        run_name(in_path=src, out_path=out)
    data = json.loads(out.read_text())
    c = data["clusters"][0]
    assert c["fallback"] is True
    assert c["name"]
    assert sorted(c["article_ids"]) == [1, 2, 3]

def test_run_name_uses_llm_when_available(tmp_path):
    clusters = {"method": "hdbscan", "items": [
        {"article_id": 1, "title": "x", "cluster_id": 0},
        {"article_id": 2, "title": "y", "cluster_id": 0},
    ]}
    src = tmp_path / "c.json"; src.write_text(json.dumps(clusters))
    out = tmp_path / "n.json"
    with patch("src.name.name_cluster",
               return_value={"name": "测试领域", "description": "desc"}):
        run_name(in_path=src, out_path=out)
    c = json.loads(out.read_text())["clusters"][0]
    assert c["name"] == "测试领域" and c["fallback"] is False
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/integration/test_name.py -v`
Expected: FAIL

- [ ] **Step 3: 写实现**

```python
# src/name.py
import argparse
import json
import os
from collections import defaultdict
from pathlib import Path
from src.lib.llm import name_cluster
from src.lib.tfidf_fallback import keyword_name

def run_name(*, in_path: Path, out_path: Path):
    payload = json.loads(in_path.read_text())
    by_cluster: dict[int, list[dict]] = defaultdict(list)
    for it in payload["items"]:
        if it["cluster_id"] == -1:
            continue
        by_cluster[it["cluster_id"]].append(it)

    clusters = []
    for cid, items in sorted(by_cluster.items()):
        titles = [i["title"] for i in items]
        fallback = False
        try:
            named = name_cluster(titles)
            name, desc = named["name"], named["description"]
        except Exception as e:
            print(f"[name] cluster {cid} LLM failed ({e}); falling back to TF-IDF")
            name = keyword_name(titles)
            desc = f"由 {len(titles)} 篇文章自动聚类（TF-IDF 兜底）"
            fallback = True
        clusters.append({
            "cluster_id": cid, "name": name, "description": desc,
            "article_ids": [i["article_id"] for i in items],
            "fallback": fallback,
        })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"clusters": clusters},
                                   ensure_ascii=False, indent=2))

def main():
    ap = argparse.ArgumentParser()
    out = os.environ.get("OUT_DIR", "out")
    ap.add_argument("--in", dest="inp", default=f"{out}/clusters.json")
    ap.add_argument("--out", default=f"{out}/clusters_named.json")
    a = ap.parse_args()
    run_name(in_path=Path(a.inp), out_path=Path(a.out))

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/integration/test_name.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/name.py tests/integration/test_name.py
git commit -m "feat(name): LLM 命名聚类并在失败时兜底 TF-IDF"
```

---

### Task 12: src/network.py — betweenness + 桥梁标记

**Files:**
- Create: `src/network.py`
- Create: `tests/unit/test_network.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_network.py
import numpy as np
from src.network import compute_edges, compute_bridges

def test_compute_edges_topk_aggregates_similarities():
    vecs = {
        1: np.array([1.0, 0.0]), 2: np.array([0.95, 0.05]),
        3: np.array([0.0, 1.0]), 4: np.array([0.05, 0.95]),
    }
    clusters = [
        {"cluster_id": 0, "article_ids": [1, 2]},
        {"cluster_id": 1, "article_ids": [3, 4]},
    ]
    edges = compute_edges(clusters, vecs, top_k=1)
    e = next(x for x in edges if {x["source"], x["target"]} == {0, 1})
    assert 0.0 <= e["weight"] < 1.0

def test_compute_bridges_returns_top_three():
    nodes = [0, 1, 2, 3]
    edges = [{"source": 0, "target": 1, "weight": 1.0},
             {"source": 1, "target": 2, "weight": 1.0},
             {"source": 2, "target": 3, "weight": 1.0}]
    bridges = compute_bridges(nodes, edges, top_n=2)
    assert len(bridges) == 2
    assert {b["cluster_id"] for b in bridges} >= {1, 2}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/unit/test_network.py -v`
Expected: FAIL

- [ ] **Step 3: 写实现**

```python
# src/network.py
import argparse
import json
import os
from itertools import combinations
from pathlib import Path
import numpy as np
import networkx as nx
from src.lib.vec import VecStore

def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))

def compute_edges(clusters: list[dict], vec_by_article: dict[int, np.ndarray],
                  *, top_k: int = 5) -> list[dict]:
    edges = []
    for a, b in combinations(clusters, 2):
        va = [vec_by_article[i] for i in a["article_ids"] if i in vec_by_article]
        vb = [vec_by_article[i] for i in b["article_ids"] if i in vec_by_article]
        if not va or not vb:
            continue
        total = 0.0
        for x in va:
            sims = sorted((_cosine(x, y) for y in vb), reverse=True)[:top_k]
            total += sum(sims)
        edges.append({"source": a["cluster_id"], "target": b["cluster_id"],
                      "weight": round(total, 4)})
    return edges

def compute_bridges(nodes: list[int], edges: list[dict], *, top_n: int = 3):
    g = nx.Graph()
    g.add_nodes_from(nodes)
    for e in edges:
        g.add_edge(e["source"], e["target"], weight=e["weight"])
    bc = nx.betweenness_centrality(g, weight="weight")
    ranked = sorted(bc.items(), key=lambda kv: kv[1], reverse=True)
    return [{"cluster_id": cid, "betweenness": round(score, 4)}
            for cid, score in ranked[:top_n]]

def build_network(*, clusters_named: dict, vec_by_article: dict[int, np.ndarray],
                  top_k: int = 5, top_n_bridges: int = 3) -> dict:
    clusters = clusters_named["clusters"]
    edges = compute_edges(clusters, vec_by_article, top_k=top_k)
    nodes = [c["cluster_id"] for c in clusters]
    bridges = compute_bridges(nodes, edges, top_n=top_n_bridges)
    return {
        "nodes": [{"cluster_id": c["cluster_id"], "name": c["name"],
                   "size": len(c["article_ids"])} for c in clusters],
        "edges": edges,
        "bridges": bridges,
    }

def run_network(*, named_path: Path, chroma_path: Path, out_path: Path):
    named = json.loads(named_path.read_text())
    store = VecStore(chroma_path)
    ids, vecs, metas = store.fetch_with_meta()
    vec_by_article = {m["article_id"]: np.asarray(v) for m, v in zip(metas, vecs)}
    payload = build_network(clusters_named=named, vec_by_article=vec_by_article)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload

def main():
    ap = argparse.ArgumentParser()
    out = os.environ.get("OUT_DIR", "out")
    ap.add_argument("--named", default=f"{out}/clusters_named.json")
    ap.add_argument("--chroma", default=os.environ.get("CHROMA_PATH", "data/chroma"))
    ap.add_argument("--out", default=f"{out}/network.json")
    a = ap.parse_args()
    p = run_network(named_path=Path(a.named), chroma_path=Path(a.chroma),
                    out_path=Path(a.out))
    print(f"nodes={len(p['nodes'])} edges={len(p['edges'])} "
          f"bridges={[b['cluster_id'] for b in p['bridges']]}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/unit/test_network.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/network.py tests/unit/test_network.py
git commit -m "feat(network): 计算簇间 Top-K 相似度边权与桥梁领域"
```

---

## Phase 3 — VitePress 发布（1-2 天）

### Task 13: VitePress 站点骨架 + Jinja2 模板

**Files:**
- Create: `site/package.json`、`site/.vitepress/config.ts`
- Create: `templates/index.md.j2`、`templates/domain.md.j2`、`templates/article.md.j2`、`templates/network.html.j2`

- [ ] **Step 1: 写 site/package.json**

```json
{
  "name": "knowledge-map-site",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vitepress dev docs",
    "build": "vitepress build docs",
    "preview": "vitepress preview docs"
  },
  "devDependencies": { "vitepress": "^1.5.0" }
}
```

- [ ] **Step 2: 写 site/.vitepress/config.ts**

```ts
import { defineConfig } from 'vitepress'

export default defineConfig({
  title: '技术文章知识地图',
  description: '53 篇技术文章的领域自动聚类与桥梁分析',
  themeConfig: {
    nav: [
      { text: '首页', link: '/' },
      { text: '领域', link: '/domains/' },
    ],
  },
})
```

- [ ] **Step 3: 写四个 Jinja2 模板**

```jinja
{# templates/index.md.j2 #}
# 技术文章知识地图

<iframe src="/network.html" width="100%" height="600" frameborder="0"></iframe>

## Top 桥梁领域

{% for b in bridges %}
- **[{{ b.name }}](/domains/{{ b.cluster_id }})** — betweenness {{ "%.4f" % b.betweenness }}
{% endfor %}

## 所有领域

{% for c in clusters %}
- [{{ c.name }}](/domains/{{ c.cluster_id }}) — {{ c.article_ids|length }} 篇 — {{ c.description }}
{% endfor %}
```

```jinja
{# templates/domain.md.j2 #}
# {{ cluster.name }}

> {{ cluster.description }}{% if cluster.fallback %} _(TF-IDF 兜底命名)_{% endif %}

**文章数**：{{ cluster.article_ids|length }}

## 文章列表

{% for a in articles %}
- [{{ a.title }}]({% if a.url %}{{ a.url }}{% else %}/articles/{{ a.id }}{% endif %}){% if a.manual_tag %} _[原分类: {{ a.manual_tag }}]_{% endif %}
{% endfor %}

## 关联领域

{% for r in related %}
- [{{ r.name }}](/domains/{{ r.cluster_id }}) — 相似度 {{ "%.2f" % r.weight }}
{% endfor %}
```

```jinja
{# templates/article.md.j2 #}
# {{ article.title }}

{% if article.url %}[阅读原文]({{ article.url }}){% else %}_未找到原文链接_{% endif %}

- **来源**：{{ article.source or "未知" }}
- **原分类**：{{ article.manual_tag or "无" }}
- **所属领域**：[{{ cluster.name }}](/domains/{{ cluster.cluster_id }})
- **收藏时间**：{{ article.added_at }}

{% if article.summary %}## 摘要

{{ article.summary }}{% endif %}
```

```jinja
{# templates/network.html.j2 #}
<!doctype html>
<html><head><meta charset="utf-8"><title>领域网络</title>
<style>body{margin:0;font-family:system-ui}svg{width:100vw;height:100vh}
.node circle{stroke:#fff;stroke-width:1.5px;cursor:pointer}
.node text{font-size:12px;pointer-events:none}
.bridge circle{stroke:#e63946;stroke-width:3px}
.link{stroke:#999;stroke-opacity:.5}</style></head>
<body><svg></svg>
<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
const data = {{ data_json | safe }};
const bridgeIds = new Set(data.bridges.map(b => b.cluster_id));
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
  .on("click", (_, d) => location.href = `/domains/${d.cluster_id}`);
node.append("circle").attr("r", d => 6 + d.size).attr("fill", "#1f77b4");
node.append("text").attr("dx", 12).attr("dy", "0.35em").text(d => d.name);
sim.on("tick", () => {
  link.attr("x1", d => d.source.x).attr("y1", d => d.source.y)
      .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
  node.attr("transform", d => `translate(${d.x},${d.y})`);
});
</script></body></html>
```

- [ ] **Step 4: 验证 vitepress 能起 dev server**

Run: `cd site && http_proxy=http://127.0.0.1:7897 https_proxy=http://127.0.0.1:7897 all_proxy=socks5://127.0.0.1:7897 pnpm install && pnpm dev`
Expected: dev server 起在 http://localhost:5173；首页会提示缺少 docs/index.md（publish 还没运行，正常）。Ctrl+C 退出。

- [ ] **Step 5: Commit**

```bash
git add site/package.json site/.vitepress/config.ts templates/
git commit -m "feat(site): VitePress 站点骨架与 Jinja2 模板"
```

---

### Task 14: src/publish.py — 渲染 markdown 与网络图

**Files:**
- Create: `src/publish.py`
- Create: `tests/unit/test_publish.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_publish.py
import json
from src.publish import render_site
from src.lib.db import init_db, get_conn, insert_article

def test_render_site_writes_index_and_domain_pages(tmp_path):
    db = tmp_path / "t.db"
    init_db(db)
    with get_conn(db) as c:
        insert_article(c, title="A", url="https://x/1", source="wechat",
                       source_name=None, manual_tag="AI", summary=None)
        insert_article(c, title="B", url=None, source=None,
                       source_name=None, manual_tag="AI", summary=None)
    named = {"clusters": [
        {"cluster_id": 0, "name": "AI Coding", "description": "desc",
         "article_ids": [1, 2], "fallback": False}
    ]}
    network = {
        "nodes": [{"cluster_id": 0, "name": "AI Coding", "size": 2}],
        "edges": [],
        "bridges": [{"cluster_id": 0, "betweenness": 0.5}],
    }
    (tmp_path / "named.json").write_text(json.dumps(named))
    (tmp_path / "net.json").write_text(json.dumps(network))
    site = tmp_path / "site"
    render_site(named_path=tmp_path/"named.json", network_path=tmp_path/"net.json",
                db=db, templates_dir="templates", site_dir=site)
    assert (site / "index.md").exists()
    assert (site / "domains" / "0.md").exists()
    assert (site / "network.html").exists()
    assert "AI Coding" in (site / "index.md").read_text()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/unit/test_publish.py -v`
Expected: FAIL — `No module named src.publish`

- [ ] **Step 3: 写实现**

```python
# src/publish.py
import argparse
import json
import os
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from src.lib.db import fetch_all_articles

def _env(templates_dir: str | Path) -> Environment:
    return Environment(loader=FileSystemLoader(str(templates_dir)),
                       autoescape=select_autoescape(["html"]),
                       keep_trailing_newline=True)

def _related(cluster_id: int, edges: list[dict], names: dict[int, str], k: int = 5):
    rels = []
    for e in edges:
        if e["source"] == cluster_id:
            rels.append((e["target"], e["weight"]))
        elif e["target"] == cluster_id:
            rels.append((e["source"], e["weight"]))
    rels.sort(key=lambda x: x[1], reverse=True)
    return [{"cluster_id": cid, "name": names.get(cid, str(cid)), "weight": w}
            for cid, w in rels[:k]]

def render_site(*, named_path: Path, network_path: Path, db: Path,
                templates_dir: str | Path, site_dir: Path):
    named = json.loads(Path(named_path).read_text())
    network = json.loads(Path(network_path).read_text())
    articles = {a["id"]: a for a in fetch_all_articles(db)}
    name_by_cid = {c["cluster_id"]: c["name"] for c in named["clusters"]}
    bridges_full = [{"cluster_id": b["cluster_id"],
                     "name": name_by_cid.get(b["cluster_id"], ""),
                     "betweenness": b["betweenness"]} for b in network["bridges"]]

    env = _env(templates_dir)
    site_dir = Path(site_dir)
    (site_dir / "domains").mkdir(parents=True, exist_ok=True)
    (site_dir / "articles").mkdir(parents=True, exist_ok=True)

    (site_dir / "index.md").write_text(
        env.get_template("index.md.j2").render(
            clusters=named["clusters"], bridges=bridges_full
        ), encoding="utf-8"
    )
    (site_dir / "network.html").write_text(
        env.get_template("network.html.j2").render(
            data_json=json.dumps(network, ensure_ascii=False)
        ), encoding="utf-8"
    )
    for c in named["clusters"]:
        page = env.get_template("domain.md.j2").render(
            cluster=c,
            articles=[articles[aid] for aid in c["article_ids"] if aid in articles],
            related=_related(c["cluster_id"], network["edges"], name_by_cid),
        )
        (site_dir / "domains" / f"{c['cluster_id']}.md").write_text(page, encoding="utf-8")
        for aid in c["article_ids"]:
            if aid not in articles:
                continue
            (site_dir / "articles" / f"{aid}.md").write_text(
                env.get_template("article.md.j2").render(article=articles[aid], cluster=c),
                encoding="utf-8",
            )

def main():
    ap = argparse.ArgumentParser()
    out = os.environ.get("OUT_DIR", "out")
    ap.add_argument("--named", default=f"{out}/clusters_named.json")
    ap.add_argument("--network", default=f"{out}/network.json")
    ap.add_argument("--db", default=os.environ.get("DB_PATH", "data/articles.db"))
    ap.add_argument("--templates", default="templates")
    ap.add_argument("--site", default=os.environ.get("SITE_DIR", "site/docs"))
    a = ap.parse_args()
    render_site(named_path=Path(a.named), network_path=Path(a.network),
                db=Path(a.db), templates_dir=a.templates, site_dir=Path(a.site))
    print(f"published to {a.site}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/unit/test_publish.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add src/publish.py tests/unit/test_publish.py
git commit -m "feat(publish): 渲染领域/文章/网络图 Markdown 与 HTML"
```

---

### Task 15: Makefile 串联 + e2e 集成测试

**Files:**
- Create: `Makefile`
- Create: `tests/integration/test_pipeline_e2e.py`

- [ ] **Step 1: 写 e2e 测试（mock 外部 API）**

```python
# tests/integration/test_pipeline_e2e.py
import json
import subprocess
from unittest.mock import patch
from src.embed import run_embed
from src.cluster import run_cluster
from src.name import run_name
from src.network import run_network
from src.publish import render_site

def test_full_pipeline_on_six_articles(tmp_path):
    idx = tmp_path / "ai.md"
    idx.write_text(
        "### AI\n\n| # | 标题 | 链接 | 来源 | 日期 |\n|---|---|---|---|---|\n"
        + "\n".join(f"| {i} | t{i} | 未找到 | x | 2026-01-01 |" for i in range(1, 7))
    )
    db = tmp_path / "t.db"
    r = subprocess.run(
        ["uv", "run", "python", "-m", "scripts.migrate_markdown",
         "--dir", str(tmp_path), "--db", str(db)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr

    vecs_a = [[1.0, 0.0, 0.0]] * 3
    vecs_b = [[0.0, 1.0, 0.0]] * 3
    with patch("src.embed.embed_texts", return_value=vecs_a + vecs_b):
        run_embed(db=db, chroma_path=tmp_path/"chroma", batch_size=10)

    run_cluster(chroma_path=tmp_path/"chroma",
                out_path=tmp_path/"clusters.json", min_cluster_size=3)

    with patch("src.name.name_cluster",
               return_value={"name": "X", "description": "y"}):
        run_name(in_path=tmp_path/"clusters.json", out_path=tmp_path/"named.json")

    run_network(named_path=tmp_path/"named.json",
                chroma_path=tmp_path/"chroma", out_path=tmp_path/"network.json")
    render_site(named_path=tmp_path/"named.json", network_path=tmp_path/"network.json",
                db=db, templates_dir="templates", site_dir=tmp_path/"site")

    assert (tmp_path/"site"/"index.md").exists()
    net = json.loads((tmp_path/"network.json").read_text())
    assert len(net["nodes"]) >= 2
```

- [ ] **Step 2: 跑测试确认通过**

Run: `uv run pytest tests/integration/test_pipeline_e2e.py -v`
Expected: 1 passed（所有前置模块均已实现，e2e 应该一次跑通；若失败按错误信息修正）

- [ ] **Step 3: 写 Makefile**

```makefile
.PHONY: migrate refresh build serve all test clean
SHELL := /bin/bash
PY := uv run python

migrate:
	$(PY) -m scripts.migrate_markdown --dir articles --db data/articles.db

refresh:
	$(PY) -m src.embed
	$(PY) -m src.cluster
	$(PY) -m src.name
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
	rm -rf out site/.vitepress/dist site/.vitepress/cache
```

- [ ] **Step 4: 跑全部测试 + 检查 Makefile 语法**

Run: `uv run pytest && make -n refresh`
Expected: 所有测试通过；`make -n refresh` 打印命令但不执行。

- [ ] **Step 5: Commit**

```bash
git add Makefile tests/integration/test_pipeline_e2e.py
git commit -m "feat(make): 添加 Makefile 串联 pipeline 与端到端集成测试"
```

---

### Task 16: 真实数据冒烟 + 回归 snapshot

**Files:**
- Create: `tests/fixtures/regression_snapshot.json`
- Create: `tests/integration/test_regression.py`

- [ ] **Step 1: 真实跑一次 migrate + refresh**

Run（需 `.env` 已配 `OPENAI_API_KEY`、`ANTHROPIC_API_KEY`）:

```bash
http_proxy=http://127.0.0.1:7897 https_proxy=http://127.0.0.1:7897 all_proxy=socks5://127.0.0.1:7897 \
  make migrate
http_proxy=http://127.0.0.1:7897 https_proxy=http://127.0.0.1:7897 all_proxy=socks5://127.0.0.1:7897 \
  make refresh
```

Expected: `data/articles.db` 有 53 行，`out/clusters_named.json` 与 `out/network.json` 生成。

- [ ] **Step 2: 人工 review 并锁定 snapshot**

人工查看 `out/clusters_named.json` 与 `out/network.json`，按 spec §9 Phase 2 验收要求确认：

1. 领域数在 5–10 之间
2. Top-3 桥梁能解释（不与原 5 个 manual_tag 完全重合）
3. 若聚类只是 manual_tag 复刻：调小 `min_cluster_size`（默认 3 → 试 2）或减小 `min_samples`，重跑 cluster + name + network
4. 调参 2-3 轮后仍无新洞察 → 停下，回 brainstorming 重议方向

满意后保存 snapshot：

```bash
uv run python -c "
import json
named = json.load(open('out/clusters_named.json'))
net = json.load(open('out/network.json'))
snap = {
    'n_clusters': len(named['clusters']),
    'bridges': sorted(b['cluster_id'] for b in net['bridges']),
    'bridge_names': sorted(
        {c['cluster_id']: c['name'] for c in named['clusters']}[b['cluster_id']]
        for b in net['bridges']
    ),
}
json.dump(snap, open('tests/fixtures/regression_snapshot.json', 'w'),
          ensure_ascii=False, indent=2)
print(snap)
"
```

- [ ] **Step 3: 写回归测试**

```python
# tests/integration/test_regression.py
import json
from pathlib import Path
import pytest

SNAP = Path("tests/fixtures/regression_snapshot.json")
NAMED = Path("out/clusters_named.json")
NET = Path("out/network.json")

@pytest.mark.skipif(not NAMED.exists(), reason="需要先 make refresh")
def test_cluster_count_within_tolerance():
    snap = json.loads(SNAP.read_text())
    named = json.loads(NAMED.read_text())
    assert abs(len(named["clusters"]) - snap["n_clusters"]) <= 1, (
        f"领域数偏移过大：{len(named['clusters'])} vs snapshot {snap['n_clusters']}"
    )

@pytest.mark.skipif(not NET.exists(), reason="需要先 make refresh")
def test_bridges_overlap_with_snapshot():
    snap = json.loads(SNAP.read_text())
    net = json.loads(NET.read_text())
    current = {b["cluster_id"] for b in net["bridges"]}
    overlap = current & set(snap["bridges"])
    assert len(overlap) >= 2, (
        f"桥梁列表与基线重合度过低：{current} vs snapshot {snap['bridges']}"
    )
```

- [ ] **Step 4: 跑回归测试确认通过**

Run: `uv run pytest tests/integration/test_regression.py -v`
Expected: 2 passed

- [ ] **Step 5: build + 浏览 + commit**

```bash
make build
# 打开 site/.vitepress/dist/index.html 或 make serve 查看交互网络图
git add tests/fixtures/regression_snapshot.json tests/integration/test_regression.py
git commit -m "test: 锁定 53 篇基线聚类回归 snapshot"
```

---

## MVP 完成验收

跑通如下命令并人工确认结果：

```bash
make test     # 所有测试通过，覆盖率 ≥ 80%
make all      # refresh + vitepress build 一气呵成
make serve    # 浏览器打开 http://localhost:5173 看交互网络图
```

确认 spec §12 的 6 项验收：

1. `make all` 一键跑通 53 篇 → 静态站
2. 首页交互网络图节点可点击
3. 每个领域一页 markdown 完整
4. 桥梁 Top-3 可解释
5. 回归 snapshot 重复跑稳定
6. 集成测试通过，单元覆盖率 ≥ 80%

把站点放本地浏览，**用一周时间问自己**（spec §9）：这张地图有没有改变我找文章 / 选下一篇读什么的方式？

- 有 → 进入二期（订阅入库 / cron / Web UI 等，按 spec §10）
- 没有 → 重新讨论核心价值假设

---

## Self-Review

- **Spec 覆盖**：决策 1-5 → Task 8（聚类）/ 11（命名）/ 12（桥梁）/ 14（按领域分组发布）全部落地；六阶段管道（ingest → embed → cluster → name → network → publish）→ Task 3-7-8-11-12-14 一一对应；§7 错误处理 → embed `__failed__`（Task 7）/ K-means fallback（Task 8）/ TF-IDF fallback（Task 11）均覆盖；§8 测试策略 → 单元 + 集成 + 回归 snapshot 齐备。
- **Placeholder 扫描**：通读全文未发现 TBD / TODO / "implement later" 等占位；每段代码完整可跑。
- **类型一致性**：`embedding_id`、`article_id`、`cluster_id` 字段名在 db / vec / cluster / name / network / publish 全链路统一；`run_embed` / `run_cluster` / `run_name` / `run_network` / `render_site` 命名风格一致；`cluster_vectors` 返回 `(labels, method)`，`build_network` 返回 `{nodes, edges, bridges}` 与下游消费者一致。

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-21-knowledge-map-mvp.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — 我每个 task 派一个 fresh subagent 实现，task 间做两阶段 review，快速迭代。

**2. Inline Execution** — 我本会话内连续执行，按 checkpoint 暂停给你审。

**Which approach?**
