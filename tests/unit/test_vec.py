from src.lib.vec import VecStore


def test_add_and_fetch(tmp_path):
    store = VecStore(tmp_path / "chroma")
    store.add(ids=["a", "b"], embeddings=[[1.0, 0.0], [0.0, 1.0]],
              metadatas=[{"article_id": 1, "title": "A"},
                         {"article_id": 2, "title": "B"}])
    ids, vecs = store.fetch_all()
    assert set(ids) == {"a", "b"}
    assert len(vecs) == 2 and len(vecs[0]) == 2


def test_persistence(tmp_path):
    p = tmp_path / "chroma"
    VecStore(p).add(ids=["a"], embeddings=[[1.0]], metadatas=[{"article_id": 1}])
    ids, _ = VecStore(p).fetch_all()
    assert ids == ["a"]
