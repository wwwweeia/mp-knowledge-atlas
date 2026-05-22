from pathlib import Path

import chromadb

COLLECTION = "articles_v1"


class VecStore:
    def __init__(self, path: Path):
        Path(path).mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(path))
        self.col = self.client.get_or_create_collection(COLLECTION)

    def add(self, *, ids: list[str], embeddings: list[list[float]],
            metadatas: list[dict]) -> None:
        self.col.add(ids=ids, embeddings=embeddings, metadatas=metadatas)

    def fetch_all(self) -> tuple[list[str], list[list[float]]]:
        res = self.col.get(include=["embeddings"])
        return res["ids"], [list(v) for v in res["embeddings"]]

    def fetch_with_meta(self):
        res = self.col.get(include=["embeddings", "metadatas"])
        return res["ids"], [list(v) for v in res["embeddings"]], res["metadatas"]
