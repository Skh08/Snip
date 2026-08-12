"""Build a primary DOCX corpus with non-duplicating HTML verification passages."""
from __future__ import annotations

import json
from pathlib import Path

from .ingest import parse_docx
from .ingest_html import parse_html
from .models import Chunk


def build(docx_path: Path, output_path: Path, html_path: Path | None = None) -> int:
    primary = parse_docx(docx_path)
    chunks: list[Chunk] = list(primary)
    primary_paragraphs = {chunk.paragraph for chunk in primary if chunk.paragraph}
    if html_path and html_path.exists():
        # Word remains authoritative. Include only web paragraphs missing from it.
        chunks.extend(chunk for chunk in parse_html(html_path) if chunk.paragraph not in primary_paragraphs)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps([chunk.model_dump() for chunk in chunks], ensure_ascii=False, indent=2), encoding="utf-8")
    return len(chunks)
