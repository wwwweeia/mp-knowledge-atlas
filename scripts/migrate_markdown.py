"""One-shot migration: read articles/*.md index files and insert into SQLite."""

import argparse
from pathlib import Path

from src.lib.db import get_conn, init_db, insert_article
from src.lib.parse import parse_index


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Migrate articles/*.md index files into SQLite."
    )
    ap.add_argument("--dir", required=True, help="Directory containing *.md index files")
    ap.add_argument("--db", required=True, help="Path to the SQLite database")
    args = ap.parse_args()

    db_path = Path(args.db)
    init_db(db_path)

    total = 0
    for md in sorted(Path(args.dir).glob("*.md")):
        if md.name == "index.md":
            continue
        rows = parse_index(md.read_text(encoding="utf-8"))
        with get_conn(db_path) as conn:
            for r in rows:
                insert_article(
                    conn,
                    title=r["title"],
                    url=r["url"],
                    source=r["source"],
                    source_name=None,
                    manual_tag=r["manual_tag"],
                    summary=None,
                )
        total += len(rows)

    print(f"inserted={total}")


if __name__ == "__main__":
    main()
