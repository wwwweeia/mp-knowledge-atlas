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
        has_fulltext = 1 if content else 0
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
            "raw_html": content if content else None,
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
