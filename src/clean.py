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
