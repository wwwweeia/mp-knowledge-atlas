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
