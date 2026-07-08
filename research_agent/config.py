"""Central configuration for the Research Agent (models, retrieval, key detection)."""
from __future__ import annotations

import os

# --- Models -----------------------------------------------------------------
# Answer synthesis (either backend; auto-selected from available keys).
CLAUDE_MODEL = os.environ.get("RESEARCH_CLAUDE_MODEL", "claude-sonnet-5")
OPENAI_MODEL = os.environ.get("RESEARCH_OPENAI_MODEL", "gpt-4o-mini")
LLM_MAX_TOKENS = 1000

# Embeddings for semantic retrieval (OpenAI). An OpenAI key is required.
EMBED_MODEL = os.environ.get("RESEARCH_EMBED_MODEL", "text-embedding-3-small")

# --- Retrieval --------------------------------------------------------------
CHUNK_TARGET_CHARS = 700     # aim for ~700-char passages
CHUNK_MAX_CHARS = 1100       # hard cap before forcing a split
TOP_K = 4                    # passages retrieved per question

# --- Key detection ----------------------------------------------------------
_PLACEHOLDER_MARKERS = ("your-", "your_", "-here", "placeholder", "changeme", "example")


def is_real_key(value: str | None) -> bool:
    """True only if *value* looks like a genuinely filled-in API key.

    Guards against .env.example placeholders being mistaken for real keys, so
    backend auto-selection picks what the user actually configured.
    """
    if not value:
        return False
    v = value.strip()
    if len(v) < 20:
        return False
    low = v.lower()
    return not any(marker in low for marker in _PLACEHOLDER_MARKERS)


def has_openai_key() -> bool:
    return is_real_key(os.environ.get("OPENAI_API_KEY"))


def has_anthropic_key() -> bool:
    return is_real_key(os.environ.get("ANTHROPIC_API_KEY"))
