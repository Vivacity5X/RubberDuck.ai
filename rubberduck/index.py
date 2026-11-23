import json
import re
from dataclasses import asdict

from .config import DATA_DIR, EMBED_MODEL
from .graph import build_graph
from .models import Chunk
from .text import tokenize_code


class Embedder:
    _model = None

    def encode(self, texts):
        if Embedder._model is None:
            from sentence_transformers import SentenceTransformer
            Embedder._model = SentenceTransformer(EMBED_MODEL)
        return Embedder._model.encode(texts, normalize_embeddings=True, batch_size=32).tolist()


class Index:
    def __init__(self, repo: str, embedder=None):
        import chromadb
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.repo = repo
        self.embedder = embedder or Embedder()
        client = chromadb.PersistentClient(path=str(DATA_DIR / "chroma"))
        name = "rd_" + re.sub(r"[^A-Za-z0-9_-]", "_", repo)[:55]
        self.col = client.get_or_create_collection(name, metadata={"hnsw:space": "cosine"})
        self._dirty, self.chunks, self._ids, self._bm25, self.graph = True, {}, [], None, None

    # ---- writes ----
    def upsert(self, chunks):
        if not chunks:
            return
        docs = [c.embed_text() for c in chunks]
        self.col.upsert(
            ids=[c.id for c in chunks], documents=docs,
            embeddings=self.embedder.encode(docs),
            metadatas=[{"path": c.path, "payload": json.dumps(asdict(c))} for c in chunks])
        self._dirty = True

    def delete_file(self, path: str):
        self.col.delete(where={"path": path})
        self._dirty = True

    # ---- reads ----
    def _refresh(self):
        if not self._dirty:
            return
        from rank_bm25 import BM25Okapi
        res = self.col.get(include=["metadatas"])
        self.chunks = {i: Chunk(**json.loads(m["payload"])) for i, m in zip(res["ids"], res["metadatas"])}
        self._ids = list(self.chunks)
        self._bm25 = BM25Okapi([tokenize_code(self.chunks[i].embed_text()) for i in self._ids]) if self._ids else None
        self.graph = build_graph(self.chunks.values())
        self._dirty = False

    def vector_search(self, query: str, n: int = 20) -> list:
        self._refresh()
        if not self._ids:
            return []
        res = self.col.query(query_embeddings=self.embedder.encode([query]), n_results=min(n, len(self._ids)))
        return res["ids"][0]

    def bm25_search(self, query: str, n: int = 20) -> list:
        self._refresh()
        if not self._bm25:
            return []
        scores = self._bm25.get_scores(tokenize_code(query))
        order = sorted(range(len(scores)), key=lambda i: -scores[i])[:n]
        return [self._ids[i] for i in order if scores[i] > 0]
