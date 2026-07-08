"""Answer synthesis with inline citations.

Backends (auto-selected from available keys):
  * "claude"  -> Anthropic Claude
  * "openai"  -> OpenAI GPT

Every backend returns the same structured result so the rest of the app is
backend-agnostic::

    {"answer_found": bool, "answer": "<markdown with [S#] cites>",
     "sources_used": [int, ...], "backend": str}
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from .config import (
    CLAUDE_MODEL,
    LLM_MAX_TOKENS,
    OPENAI_MODEL,
    has_anthropic_key,
    has_openai_key,
)
from .retrieve import Retrieved

_SYSTEM = """You are a meticulous research assistant. You answer questions ONLY \
using the numbered source passages provided. Rules:
- Cite every factual claim with the passage id in square brackets, e.g. [S2].
- Use only information present in the passages. Do NOT use outside knowledge.
- If the passages do not contain the answer, set "answer_found" to false and say \
you could not find it in the provided sources.
Respond with ONLY a JSON object."""

_PROMPT = """Question: {question}

Source passages:
{context}

Return JSON with exactly these keys:
- "answer_found": boolean (true only if the passages actually answer the question)
- "answer": string (markdown; cite claims inline with [S#]; if not found, briefly say so)
- "sources_used": array of integers (the [S#] ids you actually cited)"""


def _format_context(passages: List[Retrieved]) -> str:
    lines = []
    for r in passages:
        lines.append(f"[S{r.chunk.id}] (source: {r.chunk.source})\n{r.chunk.text}")
    return "\n\n".join(lines)


# --------------------------------------------------------------------------- #
# Backend resolution
# --------------------------------------------------------------------------- #

def resolve_answer_backend(prefer: str = "auto") -> str:
    if prefer == "claude":
        if not has_anthropic_key():
            raise RuntimeError("ANTHROPIC_API_KEY not set (needed for --llm claude).")
        return "claude"
    if prefer == "openai":
        if not has_openai_key():
            raise RuntimeError("OPENAI_API_KEY not set (needed for --llm openai).")
        return "openai"
    # auto
    if has_anthropic_key():
        return "claude"
    if has_openai_key():
        return "openai"
    raise RuntimeError(
        "No API key found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY (see .env.example)."
    )


# --------------------------------------------------------------------------- #
# Generators
# --------------------------------------------------------------------------- #

def _normalise(data: Dict[str, Any], backend: str) -> Dict[str, Any]:
    used = data.get("sources_used", []) or []
    clean_used = []
    for x in used:
        try:
            clean_used.append(int(str(x).lstrip("Ss[]").rstrip("]")))
        except (TypeError, ValueError):
            continue
    return {
        "answer_found": bool(data.get("answer_found", False)),
        "answer": (data.get("answer") or "").strip(),
        "sources_used": clean_used,
        "backend": backend,
    }


def _answer_with_claude(question: str, passages: List[Retrieved]) -> Dict[str, Any]:
    import anthropic
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=LLM_MAX_TOKENS,
        system=_SYSTEM,
        messages=[
            {"role": "user", "content": _PROMPT.format(
                question=question, context=_format_context(passages))},
            {"role": "assistant", "content": "{"},
        ],
    )
    raw = "{" + resp.content[0].text
    raw = raw[: raw.rfind("}") + 1]
    return _normalise(json.loads(raw), "claude")


def _answer_with_openai(question: str, passages: List[Retrieved]) -> Dict[str, Any]:
    from openai import OpenAI
    client = OpenAI()
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=LLM_MAX_TOKENS,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _PROMPT.format(
                question=question, context=_format_context(passages))},
        ],
    )
    return _normalise(json.loads(resp.choices[0].message.content), "openai")


def synthesize(question: str, passages: List[Retrieved], backend: str) -> Dict[str, Any]:
    if backend == "claude":
        return _answer_with_claude(question, passages)
    if backend == "openai":
        return _answer_with_openai(question, passages)
    raise ValueError(f"Unknown answer backend: {backend!r} (use 'claude' or 'openai').")
