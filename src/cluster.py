"""Cluster stage: HDBSCAN/K-means clustering + LLM naming."""

import argparse
import json
import math
import os
from collections import defaultdict
from pathlib import Path

import hdbscan
import numpy as np
from sklearn.cluster import KMeans

from src.lib.db import fetch_all_articles, init_db
from src.lib.llm import name_cluster
from src.lib.vec import VecStore

NOISE_RATIO_THRESHOLD = 0.30


def cluster_vectors(
    vectors: list[list[float]],
    *,
    min_cluster_size: int = 3,
    min_samples: int | None = None,
) -> tuple[list[int], str]:
    """Cluster vectors with HDBSCAN, falling back to K-means when too noisy."""
    arr = np.asarray(vectors, dtype=float)
    h = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric="euclidean",
    )
    labels = h.fit_predict(arr).tolist()

    noise_ratio = sum(1 for l in labels if l == -1) / max(len(labels), 1)
    if (
        noise_ratio <= NOISE_RATIO_THRESHOLD
        and len({l for l in labels if l != -1}) >= 2
    ):
        return labels, "hdbscan"

    k = max(2, round(math.sqrt(len(vectors) / 2)))
    km = KMeans(n_clusters=k, n_init=10, random_state=42)
    return km.fit_predict(arr).tolist(), "kmeans"


def run_cluster(
    *,
    chroma_path: Path,
    db: Path,
    out_path: Path,
    min_cluster_size: int = 3,
) -> dict:
    """Load vectors from ChromaDB, cluster, name clusters via LLM, write JSON."""
    init_db(db)
    store = VecStore(chroma_path)
    ids, vecs, metas = store.fetch_with_meta()

    if not ids:
        return {"method": "none", "clusters": []}

    labels, method = cluster_vectors(vecs, min_cluster_size=min_cluster_size)

    articles_map = {str(a["id"]): a for a in fetch_all_articles(db)}

    by_cluster: dict[int, list[int]] = defaultdict(list)
    for i, label in enumerate(labels):
        if label != -1:
            by_cluster[label].append(i)

    arr = np.asarray(vecs, dtype=float)

    clusters = []
    for cid, indices in sorted(by_cluster.items()):
        article_metas = [metas[i] for i in indices]
        titles = [m["title"] for m in article_metas]

        # Collect keywords from DB articles in this cluster
        cluster_keywords: set[str] = set()
        for m in article_metas:
            aid = m.get("article_id", "")
            art = articles_map.get(str(aid), articles_map.get(aid, {}))
            kws = art.get("keywords", "[]")
            try:
                cluster_keywords.update(json.loads(kws))
            except (json.JSONDecodeError, TypeError):
                pass

        # Name cluster via LLM
        try:
            named = name_cluster(titles)
            name = named["name"]
            desc = named.get("description", "")
        except Exception as e:
            print(f"[cluster] cluster {cid} naming failed: {e}")
            name = titles[0][:12] if titles else f"领域{cid}"
            desc = f"由 {len(titles)} 篇文章自动聚类"

        top_articles = []
        for i in indices[:3]:
            aid = metas[i].get("article_id", "")
            aid_str = str(aid)
            art = articles_map.get(aid_str, articles_map.get(aid, {}))
            top_articles.append({
                "id": int(aid) if isinstance(aid, int) or str(aid).isdigit() else aid,
                "title": metas[i]["title"],
                "summary": art.get("summary", ""),
            })

        clusters.append({
            "cluster_id": cid,
            "name": name,
            "description": desc,
            "keywords": sorted(cluster_keywords)[:10],
            "article_ids": [
                int(m["article_id"]) if isinstance(m["article_id"], int)
                or str(m["article_id"]).isdigit()
                else m["article_id"]
                for m in article_metas
            ],
            "top_articles": top_articles,
        })

    payload = {
        "method": method,
        "clusters": clusters,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chroma", default=os.environ.get("CHROMA_PATH", "data/chroma"))
    ap.add_argument("--db", default=os.environ.get("DB_PATH", "data/articles.db"))
    out = os.environ.get("OUT_DIR", "out")
    ap.add_argument("--out", default=f"{out}/clusters_named.json")
    ap.add_argument("--min-cluster-size", type=int, default=3)
    a = ap.parse_args()

    p = run_cluster(
        chroma_path=Path(a.chroma),
        db=Path(a.db),
        out_path=Path(a.out),
        min_cluster_size=a.min_cluster_size,
    )
    n = len(p["clusters"])
    total = sum(len(c["article_ids"]) for c in p["clusters"])
    print(f"method={p['method']} clusters={n} articles={total}")


if __name__ == "__main__":
    main()
