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
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()

def insert_article(conn: sqlite3.Connection, *, title: str, url: str | None,
                   source: str | None, source_name: str | None,
                   manual_tag: str | None, summary: str | None) -> None:
    conn.execute(
        "INSERT INTO articles (title, url, source, source_name, manual_tag, summary) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (title, url, source, source_name, manual_tag, summary),
    )

def fetch_pending_embeddings(path: Path) -> list[dict]:
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

def fetch_all_articles(path: Path) -> list[dict]:
    with get_conn(path) as c:
        rows = c.execute("SELECT * FROM articles").fetchall()
    return [dict(r) for r in rows]
