"""Naming stage: assign human-readable names to clusters via LLM, with TF-IDF fallback."""

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

from src.lib.llm import name_cluster
from src.lib.tfidf_fallback import keyword_name


def run_name(*, in_path: Path, out_path: Path) -> None:
    """Read clustering output, name each cluster, and write named results.

    For each cluster (cluster_id != -1), attempts LLM naming first.
    On any LLM failure, falls back to TF-IDF keyword extraction.
    """
    payload = json.loads(in_path.read_text())

    by_cluster: dict[int, list[dict]] = defaultdict(list)
    for item in payload["items"]:
        if item["cluster_id"] == -1:
            continue
        by_cluster[item["cluster_id"]].append(item)

    clusters = []
    for cid, items in sorted(by_cluster.items()):
        titles = [i["title"] for i in items]
        fallback = False
        try:
            named = name_cluster(titles)
            name = named["name"]
            desc = named["description"]
        except Exception as e:
            print(f"[name] cluster {cid} LLM failed ({e}); falling back to TF-IDF")
            name = keyword_name(titles)
            desc = f"由 {len(titles)} 篇文章自动聚类（TF-IDF 兜底）"
            fallback = True

        clusters.append({
            "cluster_id": cid,
            "name": name,
            "description": desc,
            "article_ids": [i["article_id"] for i in items],
            "fallback": fallback,
        })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(
        {"clusters": clusters}, ensure_ascii=False, indent=2,
    ))


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser(description="Name clusters via LLM with TF-IDF fallback")
    out = os.environ.get("OUT_DIR", "out")
    ap.add_argument("--in", dest="inp", default=f"{out}/clusters.json")
    ap.add_argument("--out", default=f"{out}/clusters_named.json")
    args = ap.parse_args()
    run_name(in_path=Path(args.inp), out_path=Path(args.out))


if __name__ == "__main__":
    main()
