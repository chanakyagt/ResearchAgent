"""Load source documents (.txt/.md/.pdf) and split them into citeable chunks."""
from __future__ import annotations

import os
import re
from typing import List, NamedTuple

from .config import CHUNK_MAX_CHARS, CHUNK_TARGET_CHARS

SUPPORTED = {".txt", ".md", ".pdf"}


class Chunk(NamedTuple):
    id: int              # 1-based citation id, e.g. cited as [S1]
    source: str          # source filename
    text: str            # chunk text


def _read_pdf(path: str) -> str:
    from pypdf import PdfReader
    reader = PdfReader(path)
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def read_document(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return _read_pdf(path)
    if ext in (".txt", ".md"):
        return _read_text(path)
    raise ValueError(f"Unsupported source type: {ext}")


def _split_paragraphs(text: str) -> List[str]:
    """Split on blank lines, then pack/again-split to respect the size targets."""
    raw = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: List[str] = []
    buf = ""
    for para in raw:
        if len(para) > CHUNK_MAX_CHARS:
            # Flush buffer, then hard-split the long paragraph by sentences.
            if buf:
                chunks.append(buf); buf = ""
            chunks.extend(_split_sentences(para))
            continue
        if len(buf) + len(para) + 1 <= CHUNK_TARGET_CHARS:
            buf = f"{buf}\n{para}".strip()
        else:
            if buf:
                chunks.append(buf)
            buf = para
    if buf:
        chunks.append(buf)
    return chunks


def _split_sentences(text: str) -> List[str]:
    sents = re.split(r"(?<=[.!?])\s+", text)
    out, buf = [], ""
    for s in sents:
        if len(buf) + len(s) + 1 <= CHUNK_TARGET_CHARS:
            buf = f"{buf} {s}".strip()
        else:
            if buf:
                out.append(buf)
            buf = s
    if buf:
        out.append(buf)
    return out


def load_chunks(folder: str) -> List[Chunk]:
    """Load every supported file in *folder* and return numbered chunks.

    Chunk ids are assigned globally in filename order so a citation [S3] maps to
    exactly one passage across the whole corpus.
    """
    chunks: List[Chunk] = []
    cid = 1
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if not os.path.isfile(path) or os.path.splitext(name)[1].lower() not in SUPPORTED:
            continue
        try:
            text = read_document(path).strip()
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] could not read {name}: {exc}")
            continue
        for piece in _split_paragraphs(text):
            chunks.append(Chunk(id=cid, source=name, text=piece))
            cid += 1
    return chunks
