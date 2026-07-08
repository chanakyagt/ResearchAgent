#!/usr/bin/env python3
"""Research Agent -- ask questions over a set of source documents, with citations.

Examples
--------
    # One question (auto-detects keys):
    python ask.py "What is Chanakya's work experience at Waves?"

    # Run the whole sample question set and save answers:
    python ask.py --batch data/questions.txt --out samples/answers.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# Make stdout UTF-8 so citations/snippets print on any console (incl. Windows).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # noqa: BLE001
    pass

from research_agent.config import TOP_K
from research_agent.pipeline import ResearchAgent


def render(result: dict) -> str:
    lines = []
    lines.append(f"Q: {result['question']}")
    status = "ANSWERED" if result["answer_found"] else "NOT FOUND IN SOURCES"
    lines.append(f"[{status}]")
    lines.append("")
    lines.append(result["answer"])
    lines.append("")
    # Citation integrity
    if result["cited_ids"]:
        ok = "OK" if result["citations_ok"] else f"HALLUCINATED {result['hallucinated_ids']}"
        lines.append(f"Citations: {['S%d' % i for i in result['cited_ids']]}  ({ok})")
    else:
        lines.append("Citations: (none)")
    # Sources considered
    lines.append("Sources retrieved:")
    for s in result["sources"]:
        mark = "*" if s["id"] in result["valid_ids"] else " "
        lines.append(f"  {mark} [S{s['id']}] {s['source']} (score {s['score']}): {s['snippet']}")
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Answer questions over source documents with citations.")
    p.add_argument("question", nargs="?", help="A question to answer.")
    p.add_argument("--batch", help="File with one question per line; answers all of them.")
    p.add_argument("--sources", default="data/sources", help="Folder of source documents.")
    p.add_argument("--llm", choices=["auto", "claude", "openai"], default="auto",
                   help="Answer backend. 'auto' picks Claude if its key is set, else GPT.")
    p.add_argument("--embed", choices=["auto", "openai"], default="auto",
                   help="Retrieval embeddings (OpenAI).")
    p.add_argument("--k", type=int, default=TOP_K, help="Passages to retrieve per question.")
    p.add_argument("--json", action="store_true", help="Emit raw JSON instead of text.")
    p.add_argument("--out", help="Write rendered output to this file too.")
    args = p.parse_args(argv)

    if not args.question and not args.batch:
        p.error("Provide a question, or --batch FILE.")
    if not os.path.isdir(args.sources):
        p.error(f"Sources folder not found: {args.sources}")

    try:
        agent = ResearchAgent(args.sources, embed_backend=args.embed, answer_backend=args.llm)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Mode -> {agent.describe()}\n")

    questions = []
    if args.question:
        questions.append(args.question)
    if args.batch:
        with open(args.batch, "r", encoding="utf-8") as fh:
            questions.extend(q.strip() for q in fh if q.strip() and not q.startswith("#"))

    rendered_all = []
    results = []
    for q in questions:
        result = agent.ask(q, k=args.k)
        results.append(result)
        block = json.dumps(result, indent=2, ensure_ascii=False) if args.json else render(result)
        print(block)
        print("\n" + "=" * 80 + "\n")
        rendered_all.append(block)

    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(("\n\n---\n\n").join(rendered_all) + "\n")
        print(f"Wrote {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
