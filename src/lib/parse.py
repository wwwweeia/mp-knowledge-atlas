import re

ROW_RE = re.compile(r"^\|\s*\d+\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
SECTION_RE = re.compile(r"^#+\s+(.+?)\s*$")

SOURCE_BY_DOMAIN = {
    "mp.weixin.qq.com": "wechat",
    "zhuanlan.zhihu.com": "zhihu",
    "zhihu.com": "zhihu",
    "blog.csdn.net": "csdn",
    "developer.aliyun.com": "aliyun",
}

def _source_from_url(url: str | None) -> str | None:
    if not url:
        return None
    for dom, src in SOURCE_BY_DOMAIN.items():
        if dom in url:
            return src
    return "other"

def parse_index(text: str) -> list[dict]:
    rows = []
    section = None
    for line in text.splitlines():
        m_sec = SECTION_RE.match(line)
        if m_sec:
            section = m_sec.group(1).strip()
            continue
        if line.startswith("|---") or "标题" in line:
            continue
        m = ROW_RE.match(line)
        if not m:
            continue
        title, link_cell = (s.strip() for s in m.groups())
        link_m = LINK_RE.search(link_cell)
        url = link_m.group(2) if link_m else None
        if url and not url.startswith("http"):
            url = None
        rows.append({
            "title": title,
            "url": url,
            "source": _source_from_url(url),
            "manual_tag": section,
        })
    return rows
