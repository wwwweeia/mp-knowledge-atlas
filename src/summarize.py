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
