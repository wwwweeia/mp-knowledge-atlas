import json
from pathlib import Path

import pytest

SNAP = Path("tests/fixtures/regression_snapshot.json")
NAMED = Path("out/clusters_named.json")
NET = Path("out/network.json")


@pytest.mark.skipif(not NAMED.exists(), reason="需要先 make refresh")
def test_cluster_count_within_tolerance():
    snap = json.loads(SNAP.read_text())
    named = json.loads(NAMED.read_text())
    assert abs(len(named["clusters"]) - snap["n_clusters"]) <= 1, (
        f"领域数偏移过大：{len(named['clusters'])} vs snapshot {snap['n_clusters']}"
    )


@pytest.mark.skipif(not NET.exists(), reason="需要先 make refresh")
def test_bridges_overlap_with_snapshot():
    snap = json.loads(SNAP.read_text())
    net = json.loads(NET.read_text())
    current = {b["cluster_id"] for b in net["bridges"]}
    overlap = current & set(snap["bridges"])
    assert len(overlap) >= 2, (
        f"桥梁列表与基线重合度过低：{current} vs snapshot {snap['bridges']}"
    )
