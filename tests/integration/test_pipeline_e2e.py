"""End-to-end integration test: full pipeline from migration to site rendering.

Every external API (embedding, LLM) is mocked so the test runs offline.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from src.cluster import run_cluster
from src.embed import run_embed
from src.name import run_name
from src.network import run_network
from src.publish import render_site


def test_full_pipeline_on_six_articles(tmp_path: Path) -> None:
    """Six articles, two clear clusters, all stages wired end to end."""

    # -- Arrange: seed markdown index -----------------------------------------
    idx = tmp_path / "ai.md"
    idx.write_text(
        "# AI\n\n"
        "| # | 标题 | 链接 |\n"
        "|---|------|------|\n"
        + "\n".join(
            f"| {i} | t{i} | 未找到 |" for i in range(1, 7)
        ),
        encoding="utf-8",
    )
    db = tmp_path / "t.db"

    # -- Stage 1: migrate markdown → SQLite -----------------------------------
    r = subprocess.run(
        [
            "uv", "run", "python", "-m", "scripts.migrate_markdown",
            "--dir", str(tmp_path), "--db", str(db),
        ],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr

    # -- Stage 2: embed (mock the embedding API) ------------------------------
    # First 3 articles share vector [1,0,0]; last 3 share [0,1,0]
    vecs_a = [[1.0, 0.0, 0.0]] * 3
    vecs_b = [[0.0, 1.0, 0.0]] * 3
    with patch("src.embed.embed_texts", return_value=vecs_a + vecs_b):
        n = run_embed(db=db, chroma_path=tmp_path / "chroma", batch_size=10)
    assert n == 6

    # -- Stage 3: cluster ------------------------------------------------------
    run_cluster(
        chroma_path=tmp_path / "chroma",
        out_path=tmp_path / "clusters.json",
        min_cluster_size=3,
    )
    clusters_raw = json.loads((tmp_path / "clusters.json").read_text())
    # Two distinct vector groups → at least 2 clusters (or noise fallback)
    unique_clusters = {
        i["cluster_id"] for i in clusters_raw["items"] if i["cluster_id"] != -1
    }
    assert len(unique_clusters) >= 2

    # -- Stage 4: name (mock the LLM) ----------------------------------------
    with patch(
        "src.name.name_cluster", return_value={"name": "X", "description": "y"}
    ):
        run_name(
            in_path=tmp_path / "clusters.json",
            out_path=tmp_path / "named.json",
        )
    named = json.loads((tmp_path / "named.json").read_text())
    assert len(named["clusters"]) >= 2

    # -- Stage 5: network -----------------------------------------------------
    run_network(
        named_path=tmp_path / "named.json",
        chroma_path=tmp_path / "chroma",
        out_path=tmp_path / "network.json",
    )
    net = json.loads((tmp_path / "network.json").read_text())
    assert len(net["nodes"]) >= 2

    # -- Stage 6: render site -------------------------------------------------
    templates_dir = Path(__file__).resolve().parent.parent.parent / "templates"
    render_site(
        named_path=tmp_path / "named.json",
        network_path=tmp_path / "network.json",
        db=db,
        templates_dir=str(templates_dir),
        site_dir=tmp_path / "site",
    )
    assert (tmp_path / "site" / "index.md").exists()
    assert (tmp_path / "site" / "network.html").exists()
