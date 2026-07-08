"""ResearchAgent: index a source folder once, then answer questions with cited,
verified answers.

    agent = ResearchAgent("data/sources")
    result = agent.ask("What is the uptime SLA on the Pro plan?")
"""
from __future__ import annotations

from typing import Any, Dict, List

from .citations import verify
from .config import TOP_K
from .embed import make_embedder
from .loader import Chunk, load_chunks
from .retrieve import Retriever
from .synthesize import resolve_answer_backend, synthesize

_BACKEND_LABEL = {"claude": "Claude", "openai": "GPT (OpenAI)"}


class ResearchAgent:
    def __init__(self, sources_folder: str, embed_backend: str = "auto",
                 answer_backend: str = "auto"):
        self.chunks: List[Chunk] = load_chunks(sources_folder)
        if not self.chunks:
            raise RuntimeError(f"No readable source documents in {sources_folder}")
        self.embedder = make_embedder(embed_backend)
        self.retriever = Retriever(self.embedder)
        self.retriever.index(self.chunks)
        self.answer_backend = resolve_answer_backend(answer_backend)

    def describe(self) -> str:
        return (f"retrieval: {self.embedder.kind} | "
                f"answers: {_BACKEND_LABEL[self.answer_backend]} | "
                f"{len(self.chunks)} chunks from "
                f"{len({c.source for c in self.chunks})} documents")

    def ask(self, question: str, k: int = TOP_K) -> Dict[str, Any]:
        passages = self.retriever.query(question, k)
        result = synthesize(question, passages, self.answer_backend)
        result = verify(result, passages)
        result["question"] = question
        return result
