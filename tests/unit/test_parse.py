from pathlib import Path
from src.lib.parse import parse_index

FIXTURE = Path("tests/fixtures/mini_index.md")

def test_parse_extracts_three_rows():
    rows = parse_index(FIXTURE.read_text())
    assert len(rows) == 3

def test_parse_assigns_manual_tag_from_section():
    rows = parse_index(FIXTURE.read_text())
    assert rows[0]["manual_tag"] == "AI Coding / Claude Code"
    assert rows[2]["manual_tag"] == "Agent 架构 / Skills"

def test_parse_url_and_source():
    rows = parse_index(FIXTURE.read_text())
    assert rows[0]["url"] == "https://mp.weixin.qq.com/s/a"
    assert rows[0]["source"] == "wechat"
    assert rows[1]["url"] is None
    assert rows[1]["source"] is None
    assert rows[2]["source"] == "zhihu"
