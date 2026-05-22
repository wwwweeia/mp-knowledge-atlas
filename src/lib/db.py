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


def backfill_fulltext(path: Path, wemp_articles: list[dict]) -> int:
    """Detect articles that now have fulltext (from We-MP-RSS), update and reset stage.
    Returns count of articles reset for re-processing."""
    if not wemp_articles:
        return 0
    wemp_by_id = {a["source_id"]: a for a in wemp_articles}
    reset = 0
    with get_conn(path) as c:
        rows = c.execute(
            "SELECT id, source_id, has_fulltext FROM articles WHERE has_fulltext = 0"
        ).fetchall()
        for r in rows:
            wemp = wemp_by_id.get(r["source_id"])
            if not wemp or not wemp.get("has_fulltext"):
                continue
            c.execute(
                "UPDATE articles SET has_fulltext = 1, raw_html = ?, "
                "pipeline_stage = 'ingested', clean_text = NULL, "
                "summary = NULL, keywords = NULL, embedding_id = NULL, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (wemp.get("raw_html"), r["id"]),
            )
            reset += 1
    return reset
