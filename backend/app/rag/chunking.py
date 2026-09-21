"""
Reading knowledge articles and splitting them into passages.

Article format (data/knowledge/*.md): a small front-matter block of
`key: value` lines between `---` markers, then Markdown. Supported keys:
slug, title, language (en|ar), source, url, specialty, evidence_level,
summary, version. No YAML dependency: the format is deliberately simple.

Chunking follows the document's structure: each heading starts a new
section, and paragraphs are packed into passages of up to ~MAX_CHARS.
A passage never mixes two sections, so its heading describes it.
"""

import re
from dataclasses import dataclass

MAX_CHARS = 900
_HEADING = re.compile(r"^(#{1,3})\s+(.*)$")


@dataclass(frozen=True)
class Passage:
    heading: str | None
    content: str


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    """Returns (metadata, body). Raises ValueError if the block is missing or malformed."""
    lines = text.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing front matter (the file must start with ---)")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise ValueError("front matter is not closed with ---") from None
    meta: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise ValueError(f"front matter line without ':': {line!r}")
        meta[key.strip()] = value.strip()
    return meta, "\n".join(lines[end + 1 :]).strip()


def _split_long(paragraph: str) -> list[str]:
    """Splits an over-long paragraph at sentence ends (., !, ?, ؟)."""
    sentences = re.split(r"(?<=[.!?؟])\s+", paragraph)
    parts, current = [], ""
    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > MAX_CHARS:
            parts.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        parts.append(current)
    return parts


def chunk_markdown(body: str) -> list[Passage]:
    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            sections[-1][1].append("\n".join(paragraph).strip())
            paragraph.clear()

    for line in body.splitlines():
        heading = _HEADING.match(line)
        if heading:
            flush_paragraph()
            sections.append((heading.group(2).strip(), []))
        elif not line.strip():
            flush_paragraph()
        else:
            paragraph.append(line.rstrip())
    flush_paragraph()

    passages: list[Passage] = []
    for heading, paragraphs in sections:
        current = ""
        for para in (p for raw in paragraphs for p in ([raw] if len(raw) <= MAX_CHARS else _split_long(raw))):
            if current and len(current) + len(para) + 2 > MAX_CHARS:
                passages.append(Passage(heading, current))
                current = para
            else:
                current = f"{current}\n\n{para}" if current else para
        if current:
            passages.append(Passage(heading, current))
    return passages
