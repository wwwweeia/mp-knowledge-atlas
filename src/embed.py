import argparse
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv

from src.lib.db import fetch_pending_embeddings, init_db, mark_embedded
from src.lib.embedding import embed_texts
from src.lib.vec import VecStore


def _text_for(row: dict) -> str:
    """Combine title and summary for embedding. Skip summary if it duplicates title."""
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
        metas = [{"article_id": r["id"], "title": r["title"]} for r in batch]
        store.add(ids=ids, embeddings=vecs, metadatas=metas)

        for r, eid in zip(batch, ids):
            mark_embedded(db, r["id"], eid)
        done += len(batch)

    return done


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--db", default=os.environ.get("DB_PATH", "data/articles.db")
    )
    ap.add_argument(
        "--chroma", default=os.environ.get("CHROMA_PATH", "data/chroma")
    )
    a = ap.parse_args()
    n = run_embed(db=Path(a.db), chroma_path=Path(a.chroma))
    print(f"embedded={n}")


if __name__ == "__main__":
    main()
