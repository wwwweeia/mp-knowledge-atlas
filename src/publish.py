"""渲染领域/文章/网络图 Markdown 与 HTML."""

import argparse
import json
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.lib.db import fetch_all_articles


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
    named = json.loads(Path(named_path).read_text())
    network = json.loads(Path(network_path).read_text())
    articles = {a["id"]: a for a in fetch_all_articles(db)}
    name_by_cid = {c["cluster_id"]: c["name"] for c in named["clusters"]}
    bridges_full = [
        {
            "cluster_id": b["cluster_id"],
            "name": name_by_cid.get(b["cluster_id"], ""),
            "betweenness": b["betweenness"],
        }
        for b in network["bridges"]
    ]

    env = _env(templates_dir)
    site_dir = Path(site_dir)
    (site_dir / "domains").mkdir(parents=True, exist_ok=True)
    (site_dir / "articles").mkdir(parents=True, exist_ok=True)

    (site_dir / "index.md").write_text(
        env.get_template("index.md.j2").render(
            clusters=named["clusters"], bridges=bridges_full
        ),
        encoding="utf-8",
    )
    (site_dir / "network.html").write_text(
        env.get_template("network.html.j2").render(
            data_json=json.dumps(network, ensure_ascii=False)
        ),
        encoding="utf-8",
    )
    for c in named["clusters"]:
        page = env.get_template("domain.md.j2").render(
            cluster=c,
            articles=[articles[aid] for aid in c["article_ids"] if aid in articles],
            related=_related(c["cluster_id"], network["edges"], name_by_cid),
        )
        (site_dir / "domains" / f"{c['cluster_id']}.md").write_text(
            page, encoding="utf-8"
        )
        for aid in c["article_ids"]:
            if aid not in articles:
                continue
            (site_dir / "articles" / f"{aid}.md").write_text(
                env.get_template("article.md.j2").render(
                    article=articles[aid], cluster=c
                ),
                encoding="utf-8",
            )


def main() -> None:
    ap = argparse.ArgumentParser(description="渲染知识地图站点")
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
