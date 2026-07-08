"""In-memory vector index: embed chunks, retrieve top-k by cosine similarity."""
from __future__ import annotations

from typing import List, NamedTuple

from .loader import Chunk


class Retrieved(NamedTuple):
    chunk: Chunk
    score: float


class Retriever:
    def __init__(self, embedder):
        self.embedder = embedder
        self.chunks: List[Chunk] = []
        self._doc_reps: list = []

    def index(self, chunks: List[Chunk]) -> None:
        self.chunks = chunks
        texts = [c.text for c in chunks]
        self.embedder.fit(texts)
        self._doc_reps = self.embedder.encode(texts)

    def query(self, question: str, k: int) -> List[Retrieved]:
        if not self.chunks:
            return []
        q_rep = self.embedder.encode([question])[0]
        scored = [
            Retrieved(chunk, self.embedder.similarity(q_rep, rep))
            for chunk, rep in zip(self.chunks, self._doc_reps)
        ]
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:k]
