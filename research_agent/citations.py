"""Verify that the citations in an answer point at genuinely retrieved passages.

This is the agent's honesty check: an LLM can invent a "[S9]" that was never
retrieved, or cite a passage that wasn't in context. We cross-check every [S#]
marker in the answer against the ids actually sent to the model, and surface any
that don't match -- so a reviewer can trust the citations.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from .retrieve import Retrieved

_CITE_RE = re.compile(r"\[S(\d+)\]")


def markers_in(text: str) -> List[int]:
    """Return the distinct [S#] ids referenced in *text*, in order of appearance."""
    seen, out = set(), []
    for m in _CITE_RE.finditer(text):
        i = int(m.group(1))
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def verify(result: Dict[str, Any], passages: List[Retrieved]) -> Dict[str, Any]:
    """Annotate *result* with citation verification against *passages*.

    Adds:
      cited_ids      -> ids referenced in the answer text
      valid_ids      -> cited ids that were actually retrieved
      hallucinated   -> cited ids that were NOT retrieved (should be empty)
      sources        -> [{id, source, snippet}] for each retrieved passage
    """
    retrieved_ids = {r.chunk.id for r in passages}
    cited = markers_in(result.get("answer", ""))
    valid = [i for i in cited if i in retrieved_ids]
    hallucinated = [i for i in cited if i not in retrieved_ids]

    sources = [
        {"id": r.chunk.id, "source": r.chunk.source, "score": round(r.score, 4),
         "snippet": (r.chunk.text[:220] + "...") if len(r.chunk.text) > 220 else r.chunk.text}
        for r in passages
    ]

    out = dict(result)
    out.update({
        "cited_ids": cited,
        "valid_ids": valid,
        "hallucinated_ids": hallucinated,
        "citations_ok": not hallucinated,
        "sources": sources,
    })
    return out
