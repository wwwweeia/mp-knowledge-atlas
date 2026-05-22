# src/lib/html.py
"""HTML cleaning utilities for WeChat public account articles."""

import re

from bs4 import BeautifulSoup

MAX_TEXT_LENGTH = 10000

FOOTER_PATTERNS = [
    re.compile(r"长按.{0,4}关注"),
    re.compile(r"扫码.{0,4}关注"),
    re.compile(r"点击.{0,6}在看"),
    re.compile(r"分享.{0,4}朋友圈"),
    re.compile(r"更多精彩.*关注"),
    re.compile(r"点赞.*在看.*分享"),
]


def _remove_footer_ctas(text: str) -> str:
    """Remove call-to-action footer lines common in WeChat articles."""
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        if any(p.search(line) for p in FOOTER_PATTERNS):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def clean_html(html: str) -> str:
    """Clean raw HTML: strip scripts, ads, footers. Return plain text."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    text = _remove_footer_ctas(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]
    return text


def extract_text(html: str) -> str:
    """Alias for clean_html, for readability in call sites."""
    return clean_html(html)
