# src/publish.py
"""Render VitePress site from pipeline outputs."""

import argparse
import json
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.lib.db import fetch_all_articles, init_db


def _env(templates_dir: str | Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html"]),
        keep_trailing_newline=True,
    )


def _related(
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
        {"cluster_id": cid, "name": names.get(cid, str(cid)), "weight": w}
        for cid, w in rels[:k]
    ]


def render_site(
    *,
    named_path: Path,
    network_path: Path,
    db: Path,
    templates_dir: str | Path,
    site_dir: Path,
) -> None:
    init_db(db)
    named = json.loads(Path(named_path).read_text())
    network = json.loads(Path(network_path).read_text())
    articles = {str(a["id"]): a for a in fetch_all_articles(db)}
    name_by_cid = {c["cluster_id"]: c["name"] for c in named["clusters"]}

    bridges_full = [
        {
            "cluster_id": b["cluster_id"],
            "name": name_by_cid.get(b["cluster_id"], ""),
            "betweenness": b["betweenness"],
        }
        for b in network["bridges"]
    ]

    # Recent articles sorted by published_at desc
    all_articles_sorted = sorted(
        articles.values(),
        key=lambda a: a.get("published_at") or "",
        reverse=True,
    )
    recent = all_articles_sorted[:20]

    env = _env(templates_dir)
    site_dir = Path(site_dir)
    (site_dir / "domains").mkdir(parents=True, exist_ok=True)
    (site_dir / "articles").mkdir(parents=True, exist_ok=True)

    (site_dir / "index.md").write_text(
        env.get_template("index.md.j2").render(
            clusters=named["clusters"],
            bridges=bridges_full,
            recent_articles=recent,
        ),
        encoding="utf-8",
    )

    network_html = env.get_template("network.html.j2").render(
        data_json=json.dumps(network, ensure_ascii=False)
    )
    (site_dir / "network.html").write_text(network_html, encoding="utf-8")
    (site_dir / "public").mkdir(parents=True, exist_ok=True)
    (site_dir / "public" / "network.html").write_text(network_html, encoding="utf-8")

    for c in named["clusters"]:
        cluster_articles = [
            articles[aid] for aid in (str(a) for a in c["article_ids"])
            if aid in articles
        ]
        page = env.get_template("domain.md.j2").render(
            cluster=c,
            articles=cluster_articles,
            top_articles=c.get("top_articles", []),
            related=_related(c["cluster_id"], network["edges"], name_by_cid),
        )
        (site_dir / "domains" / f"{c['cluster_id']}.md").write_text(
            page, encoding="utf-8",
        )

        for aid in c["article_ids"]:
            aid_str = str(aid)
            if aid_str not in articles:
                continue
            art = articles[aid_str]
            keywords_list = []
            try:
                keywords_list = json.loads(art.get("keywords", "[]"))
            except (json.JSONDecodeError, TypeError):
                pass
            (site_dir / "articles" / f"{aid}.md").write_text(
                env.get_template("article.md.j2").render(
                    article=art, cluster=c, keywords_list=keywords_list,
                ),
                encoding="utf-8",
            )


def main() -> None:
    ap = argparse.ArgumentParser()
    out = os.environ.get("OUT_DIR", "out")
    ap.add_argument("--named", default=f"{out}/clusters_named.json")
    ap.add_argument("--network", default=f"{out}/network.json")
    ap.add_argument("--db", default=os.environ.get("DB_PATH", "data/articles.db"))
    ap.add_argument("--templates", default="templates")
    ap.add_argument("--site", default=os.environ.get("SITE_DIR", "site/docs"))
    a = ap.parse_args()
    render_site(
        named_path=Path(a.named),
        network_path=Path(a.network),
        db=Path(a.db),
        templates_dir=a.templates,
        site_dir=Path(a.site),
    )
    print(f"published to {a.site}")


if __name__ == "__main__":
    main()
