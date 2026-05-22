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
