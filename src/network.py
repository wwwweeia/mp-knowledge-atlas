"""Network analysis: inter-cluster edge weights and bridge detection."""

import argparse
import json
import os
from itertools import combinations
from pathlib import Path

import networkx as nx
import numpy as np

from src.lib.vec import VecStore


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def compute_edges(
    clusters: list[dict],
    vec_by_article: dict[int, np.ndarray],
    *,
    top_k: int = 5,
) -> list[dict]:
    """Compute weighted edges between every pair of clusters.

    For each pair (A, B), sum the top-K cosine similarities from every
    article in A to every article in B.  The resulting weight captures
    cross-cluster semantic affinity.
    """
    edges = []
    for a, b in combinations(clusters, 2):
        va = [vec_by_article[i] for i in a["article_ids"] if i in vec_by_article]
        vb = [vec_by_article[i] for i in b["article_ids"] if i in vec_by_article]
        if not va or not vb:
            continue
        total = 0.0
        for x in va:
            sims = sorted((_cosine(x, y) for y in vb), reverse=True)[:top_k]
            total += sum(sims)
        edges.append(
            {
                "source": a["cluster_id"],
                "target": b["cluster_id"],
                "weight": round(total, 4),
            }
        )
    return edges


def compute_bridges(
    nodes: list[int],
    edges: list[dict],
    *,
    top_n: int = 3,
) -> list[dict]:
    """Rank clusters by betweenness centrality and return the top-N bridges."""
    g = nx.Graph()
    g.add_nodes_from(nodes)
    for e in edges:
        g.add_edge(e["source"], e["target"], weight=e["weight"])

    bc = nx.betweenness_centrality(g, weight="weight")
    ranked = sorted(bc.items(), key=lambda kv: kv[1], reverse=True)
    return [
        {"cluster_id": cid, "betweenness": round(score, 4)}
        for cid, score in ranked[:top_n]
    ]


def build_network(
    *,
    clusters_named: dict,
    vec_by_article: dict[int, np.ndarray],
    top_k: int = 5,
    top_n_bridges: int = 3,
) -> dict:
    """Build the full network payload: nodes, edges, bridges."""
    clusters = clusters_named["clusters"]
    edges = compute_edges(clusters, vec_by_article, top_k=top_k)
    nodes = [c["cluster_id"] for c in clusters]
    bridges = compute_bridges(nodes, edges, top_n=top_n_bridges)
    return {
        "nodes": [
            {
                "cluster_id": c["cluster_id"],
                "name": c["name"],
                "size": len(c["article_ids"]),
            }
            for c in clusters
        ],
        "edges": edges,
        "bridges": bridges,
    }


def run_network(
    *,
    named_path: Path,
    chroma_path: Path,
    out_path: Path,
) -> dict:
    """Load named clusters + vectors, compute network, write JSON."""
    named = json.loads(named_path.read_text())
    store = VecStore(chroma_path)
    ids, vecs, metas = store.fetch_with_meta()
    vec_by_article = {
        m["article_id"]: np.asarray(v) for m, v in zip(metas, vecs)
    }
    payload = build_network(clusters_named=named, vec_by_article=vec_by_article)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def main() -> None:
    ap = argparse.ArgumentParser()
    out = os.environ.get("OUT_DIR", "out")
    ap.add_argument("--named", default=f"{out}/clusters_named.json")
    ap.add_argument("--chroma", default=os.environ.get("CHROMA_PATH", "data/chroma"))
    ap.add_argument("--out", default=f"{out}/network.json")
    a = ap.parse_args()
    p = run_network(
        named_path=Path(a.named),
        chroma_path=Path(a.chroma),
        out_path=Path(a.out),
    )
    print(
        f"nodes={len(p['nodes'])} edges={len(p['edges'])} "
        f"bridges={[b['cluster_id'] for b in p['bridges']]}"
    )


if __name__ == "__main__":
    main()
