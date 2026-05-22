# tests/unit/test_html.py
from src.lib.html import clean_html, extract_text


def test_clean_html_strips_scripts():
    html = '<p>Hello</p><script>alert("xss")</script><p>World</p>'
    result = clean_html(html)
    assert "alert" not in result
    assert "Hello" in result
    assert "World" in result


def test_clean_html_removes_footer_cta():
    html = '<p>正文内容</p><p>长按关注公众号</p><p>扫码关注</p>'
    result = clean_html(html)
    assert "长按关注" not in result
    assert "扫码关注" not in result
    assert "正文内容" in result


def test_clean_html_truncates_long_text():
    html = "<p>" + "A" * 20000 + "</p>"
    result = clean_html(html)
    assert len(result) <= 10100


def test_extract_text_returns_plain_text():
    html = "<div><h1>标题</h1><p>段落1</p><p>段落2</p></div>"
    result = extract_text(html)
    assert "标题" in result
    assert "段落1" in result
    assert "<" not in result


def test_extract_text_preserves_code_blocks():
    html = "<pre><code>def foo():\n    pass</code></pre>"
    result = extract_text(html)
    assert "def foo" in result
