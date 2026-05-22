import argparse
import json
import math
import os
from pathlib import Path

import hdbscan
import numpy as np
from sklearn.cluster import KMeans

from src.lib.vec import VecStore

NOISE_RATIO_THRESHOLD = 0.30


def cluster_vectors(
    vectors: list[list[float]],
    *,
    min_cluster_size: int = 3,
    min_samples: int | None = None,
) -> tuple[list[int], str]:
    """对向量列表做聚类，优先用 HDBSCAN，噪音过高时回退到 K-means。

    Returns:
        (labels, method) — labels 里 -1 表示噪音点（仅 HDBSCAN 可能出现）。
    """
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

    # 回退：K-means，簇数取 sqrt(n/2)，至少 2
    k = max(2, round(math.sqrt(len(vectors) / 2)))
    km = KMeans(n_clusters=k, n_init=10, random_state=42)
    return km.fit_predict(arr).tolist(), "kmeans"


def run_cluster(
    *,
    chroma_path: Path,
    out_path: Path,
    min_cluster_size: int = 3,
) -> dict:
    """从 Chroma 读取向量并聚类，结果写入 JSON 文件。"""
    store = VecStore(chroma_path)
    ids, vecs, metas = store.fetch_with_meta()

    if not ids:
        return {"method": "none", "items": []}

    labels, method = cluster_vectors(vecs, min_cluster_size=min_cluster_size)

    payload = {
        "method": method,
        "items": [
            {
                "embedding_id": ids[i],
                "article_id": metas[i]["article_id"],
                "title": metas[i]["title"],
                "cluster_id": int(labels[i]),
            }
            for i in range(len(ids))
        ],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--chroma", default=os.environ.get("CHROMA_PATH", "data/chroma")
    )
    ap.add_argument(
        "--out", default=os.environ.get("OUT_DIR", "out") + "/clusters.json"
    )
    ap.add_argument("--min-cluster-size", type=int, default=3)
    a = ap.parse_args()

    p = run_cluster(
        chroma_path=Path(a.chroma),
        out_path=Path(a.out),
        min_cluster_size=a.min_cluster_size,
    )
    n_clusters = len(
        {i["cluster_id"] for i in p["items"] if i["cluster_id"] != -1}
    )
    print(f"method={p['method']} clusters={n_clusters} items={len(p['items'])}")


if __name__ == "__main__":
    main()
