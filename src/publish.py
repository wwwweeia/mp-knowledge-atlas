# src/publish.py
"""Generate data.json for the SPA frontend."""

import argparse
import json
import os
from pathlib import Path

from src.lib.db import fetch_all_articles, init_db


def _related_domains(
    cluster_id: int,
    edges: list[dict],
    names: dict[int, str],
    k: int = 5,
) -> list[dict]:
    rels: list[tuple[int, float]] = []
    for e in edges:
        if e["source"] == cluster_id:
            rels.append((e["target"], e["weight"]))
        elif e["target"] == cluster_id:
            rels.append((e["source"], e["weight"]))
    rels.sort(key=lambda x: x[1], reverse=True)
    return [
        {"id": cid, "name": names.get(cid, str(cid)), "similarity": round(w, 4)}
        for cid, w in rels[:k]
    ]


def _parse_keywords(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def generate_data_json(
    *,
    named_path: Path,
    network_path: Path,
    db: Path,
    output_path: Path,
) -> None:
    init_db(db)
    named = json.loads(named_path.read_text(encoding="utf-8"))
    network = json.loads(network_path.read_text(encoding="utf-8"))
    all_articles = {str(a["id"]): a for a in fetch_all_articles(db)}

    bridge_ids = {b["cluster_id"]: b["betweenness"] for b in network["bridges"]}
    name_by_cid = {c["cluster_id"]: c["name"] for c in named["clusters"]}

    domains = []
    for c in named["clusters"]:
        cid = c["cluster_id"]
        cluster_articles = []
        seen_ids: set[int] = set()
        for aid in c["article_ids"]:
            art = all_articles.get(str(aid))
            if not art or art["id"] in seen_ids:
                continue
            seen_ids.add(art["id"])
            cluster_articles.append({
                "id": art["id"],
                "title": art["title"],
                "url": art["url"],
                "source": art["feed_name"],
                "date": (art["published_at"] or "")[:10],
                "keywords": _parse_keywords(art.get("keywords")),
                "summary": art.get("summary") or "",
            })

        domains.append({
            "id": cid,
            "name": c["name"],
            "description": c.get("description", ""),
            "article_count": len(cluster_articles),
            "keywords": c.get("keywords", []),
            "is_bridge": cid in bridge_ids,
            "betweenness": bridge_ids.get(cid, 0),
            "articles": cluster_articles,
            "related_domains": _related_domains(
                cid, network["edges"], name_by_cid,
            ),
        })

    all_sorted = sorted(
        all_articles.values(),
        key=lambda a: a.get("published_at") or "",
        reverse=True,
    )
    recent = [
        {
            "id": a["id"],
            "title": a["title"],
            "domain_id": 0,
            "domain_name": "",
            "date": (a["published_at"] or "")[:10],
            "source": a.get("feed_name", ""),
        }
        for a in all_sorted[:20]
    ]

    article_to_domain = {}
    for d in domains:
        for art in d["articles"]:
            article_to_domain[art["id"]] = (d["id"], d["name"])
    for r in recent:
        did, dname = article_to_domain.get(r["id"], (0, ""))
        r["domain_id"] = did
        r["domain_name"] = dname

    data = {
        "stats": {
            "total_articles": len(all_articles),
            "total_domains": len(domains),
            "bridge_domains": len(bridge_ids),
            "sources": len({a["feed_name"] for a in all_articles.values()}),
        },
        "domains": domains,
        "network": {
            "nodes": [
                {
                    "id": n["cluster_id"],
                    "name": n["name"],
                    "size": n["size"],
                    "is_bridge": n["cluster_id"] in bridge_ids,
                }
                for n in network["nodes"]
            ],
            "edges": [
                {"source": e["source"], "target": e["target"], "weight": e["weight"]}
                for e in network["edges"]
            ],
        },
        "recent_articles": recent,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    out = os.environ.get("OUT_DIR", "out")
    ap.add_argument("--named", default=f"{out}/clusters_named.json")
    ap.add_argument("--network", default=f"{out}/network.json")
    ap.add_argument("--db", default=os.environ.get("DB_PATH", "data/articles.db"))
    ap.add_argument("--output", default=os.environ.get("DATA_JSON_PATH", "site/data/data.json"))
    a = ap.parse_args()
    generate_data_json(
        named_path=Path(a.named),
        network_path=Path(a.network),
        db=Path(a.db),
        output_path=Path(a.output),
    )
    print(f"generated {a.output}")


if __name__ == "__main__":
    main()
