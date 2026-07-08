"""Embedding backend for retrieval.

Retrieval uses OpenAI embeddings (`text-embedding-3-small` by default): dense
semantic vectors compared by cosine similarity.
"""
from __future__ import annotations

import math
from typing import List

from .config import EMBED_MODEL, has_openai_key


def cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class OpenAIEmbedder:
    kind = f"OpenAI {EMBED_MODEL}"

    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI()

    def fit(self, corpus: List[str]) -> None:  # stateless; kept for a uniform interface
        pass

    def encode(self, texts: List[str]) -> List[List[float]]:
        # The API accepts a batch; results come back in input order.
        resp = self.client.embeddings.create(model=EMBED_MODEL, input=texts)
        return [d.embedding for d in resp.data]

    @staticmethod
    def similarity(a, b) -> float:
        return cosine(a, b)


def make_embedder(prefer: str = "auto"):
    """Return the OpenAI embedder. Requires an OpenAI key (retrieval needs embeddings)."""
    if not has_openai_key():
        raise RuntimeError(
            "OPENAI_API_KEY is required for retrieval embeddings (see .env.example)."
        )
    return OpenAIEmbedder()
