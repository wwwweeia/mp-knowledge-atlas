import sqlite3
from unittest.mock import patch

from src.lib.db import get_conn, init_db, insert_article
from src.embed import run_embed


def test_run_embed_marks_articles_and_writes_chroma(tmp_path):
    db = tmp_path / "t.db"
    init_db(db)
    with get_conn(db) as c:
        for i in range(3):
            insert_article(
                c,
                title=f"t{i}",
                url=None,
                source=None,
                source_name=None,
                manual_tag="ai",
                summary=None,
            )

    with patch("src.embed.embed_texts", return_value=[[0.1, 0.2]] * 3):
        n = run_embed(db=db, chroma_path=tmp_path / "chroma", batch_size=10)

    assert n == 3
    with sqlite3.connect(db) as conn:
        pending = conn.execute(
            "SELECT COUNT(*) FROM articles "
            "WHERE embedding_id IS NULL OR embedding_id='__failed__'"
        ).fetchone()[0]
    assert pending == 0
