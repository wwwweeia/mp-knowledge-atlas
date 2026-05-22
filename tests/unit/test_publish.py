import json
from src.publish import render_site
from src.lib.db import init_db, get_conn, insert_article


def test_render_site_writes_index_and_domain_pages(tmp_path):
    db = tmp_path / "t.db"
    init_db(db)
    with get_conn(db) as c:
        insert_article(c, title="A", url="https://x/1", source="wechat",
                       source_name=None, manual_tag="AI", summary=None)
        insert_article(c, title="B", url=None, source=None,
                       source_name=None, manual_tag="AI", summary=None)
    named = {"clusters": [
        {"cluster_id": 0, "name": "AI Coding", "description": "desc",
         "article_ids": [1, 2], "fallback": False}
    ]}
    network = {
        "nodes": [{"cluster_id": 0, "name": "AI Coding", "size": 2}],
        "edges": [],
        "bridges": [{"cluster_id": 0, "betweenness": 0.5}],
    }
    (tmp_path / "named.json").write_text(json.dumps(named))
    (tmp_path / "net.json").write_text(json.dumps(network))
    site = tmp_path / "site"
    render_site(named_path=tmp_path/"named.json", network_path=tmp_path/"net.json",
                db=db, templates_dir="templates", site_dir=site)
    assert (site / "index.md").exists()
    assert (site / "domains" / "0.md").exists()
    assert (site / "network.html").exists()
    assert "AI Coding" in (site / "index.md").read_text()
