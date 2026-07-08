"""Offline tests: chunking, citation parsing/verification, and the answer path.
No API key or network required."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from research_agent import citations                     # noqa: E402
from research_agent.loader import Chunk, load_chunks       # noqa: E402
from research_agent.retrieve import Retrieved              # noqa: E402

SOURCES = os.path.join(os.path.dirname(__file__), "..", "data", "sources")


def test_chunking_assigns_sequential_ids():
    chunks = load_chunks(SOURCES)
    assert len(chunks) >= 5
    assert [c.id for c in chunks] == list(range(1, len(chunks) + 1))
    assert all(c.source.endswith((".md", ".txt", ".pdf")) for c in chunks)


def test_markers_in_parses_citation_ids():
    assert citations.markers_in("A [S1] then [S3] and again [S1].") == [1, 3]


def test_verify_flags_hallucinated_citation():
    passages = [Retrieved(Chunk(1, "a.md", "text one"), 0.9),
                Retrieved(Chunk(2, "b.md", "text two"), 0.5)]
    # Answer cites [S2] (valid) and [S9] (never retrieved -> hallucinated).
    result = {"answer": "Claim one [S2]. Claim two [S9].", "answer_found": True,
              "sources_used": [2, 9]}
    out = citations.verify(result, passages)
    assert out["valid_ids"] == [2]
    assert out["hallucinated_ids"] == [9]
    assert out["citations_ok"] is False


def test_openai_synthesis_mock(monkeypatch=None):
    import json
    import types
    import openai
    from research_agent import synthesize as syn

    class _Chat:
        def create(self, model, max_tokens, response_format, messages):
            body = json.dumps({"answer_found": True,
                               "answer": "The Pro plan is 99.99% [S9].",
                               "sources_used": [9]})
            return types.SimpleNamespace(
                choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=body))])

    class FakeOpenAI:
        chat = types.SimpleNamespace(completions=_Chat())

    orig = openai.OpenAI
    openai.OpenAI = lambda *a, **k: FakeOpenAI()
    try:
        passages = [Retrieved(Chunk(9, "05_sla.md", "Pro plan 99.99%"), 0.8)]
        out = syn.synthesize("uptime?", passages, "openai")
        assert out["answer_found"] and out["sources_used"] == [9]
        assert out["backend"] == "openai"
    finally:
        openai.OpenAI = orig


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print(f"PASS {name}")
            except AssertionError as e:
                failures += 1; print(f"FAIL {name}: {e}")
    print(f"\n{'All tests passed.' if not failures else str(failures) + ' failed.'}")
    raise SystemExit(1 if failures else 0)
