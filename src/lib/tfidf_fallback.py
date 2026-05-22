import jieba.analyse

STOP = {"的", "了", "是", "在", "和", "与", "或", "及"}


def keyword_name(titles: list[str], *, top_k: int = 3) -> str:
    text = "\n".join(titles)
    words = jieba.analyse.extract_tags(
        text, topK=top_k * 3, allowPOS=("n", "nz", "vn", "eng")
    )
    cleaned = [w for w in words if w not in STOP and len(w) > 1]
    if not cleaned:
        cleaned = [t.strip() for t in titles if t.strip()][:top_k]
    return " / ".join(cleaned[:top_k]) or "未命名"
