# Retrieval & citation method note

The required note explaining the retrieval/tool approach and how citations are
kept honest.

## Pipeline

```
load documents -> chunk -> embed -> retrieve top-k -> synthesise with [S#] -> verify citations
```

## 1. Chunking (`loader.py`)

Documents (`.md`/`.txt`/`.pdf`) are split on blank lines into paragraphs, then
**packed** toward a ~700-character target (hard cap 1100), with over-long
paragraphs split by sentence. Each resulting passage gets a **global id** in
filename order, so a citation `[S3]` maps to exactly one passage across the whole
corpus. Each chunk remembers its source filename for display.

## 2. Retrieval (`embed.py`, `retrieve.py`)

Every chunk is turned into a vector; the query is turned into a vector the same
way; we score all chunks by **cosine similarity** and take the top *k* (default 4).

Retrieval uses **OpenAI embeddings** (`text-embedding-3-small`): dense semantic
vectors that match meaning even when the question's wording differs from the
document, which lexical matching would miss.

## 3. Synthesis (`synthesize.py`)

The retrieved passages are formatted as a numbered context (`[S1] (source: …)`),
and the LLM is instructed to:

- answer **using only** those passages,
- **cite every claim** with `[S#]`,
- set `answer_found = false` and say so if the passages don't contain the answer.

Output is forced to JSON (`{answer_found, answer, sources_used}`) — via assistant
prefill for Claude, JSON mode for GPT. The two backends are interchangeable and
auto-selected (Claude when its key is set, otherwise GPT).

## 4. Citation verification (`citations.py`) — the honesty check

An LLM can fabricate a citation (`[S9]` that was never retrieved) or cite a passage
that wasn't in context. So after synthesis the agent:

1. parses every `[S#]` marker in the answer,
2. splits them into **valid** (id was retrieved) and **hallucinated** (id was not),
3. sets `citations_ok = (no hallucinated ids)`.

The CLI and GUI display this, and any hallucinated citation is flagged loudly.
Across the committed sample run over the résumé, **0 hallucinated citations**
occurred and the 2 out-of-scope questions were correctly refused.

## Why this avoids hallucination

- The answer is constrained to **retrieved passages**, not open-ended generation.
- The model is told to **refuse** when the passages don't answer the question, and
  the sample set proves it does.
- Every citation is **checked against provenance**, so a reviewer can verify each
  claim against the exact passage shown.

### Honest scope of the check
Verification confirms a cited passage **was retrieved** (provenance). It does not
yet confirm the passage **entails** the sentence — that would need a natural-language
inference step, which is listed as future work.
