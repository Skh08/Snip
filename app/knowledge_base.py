"""Build a primary DOCX corpus with non-duplicating HTML verification passages."""
from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from .ingest import parse_docx
from .ingest_html import parse_html
from .models import Chunk


def _comparison_text(value: str) -> str:
    """Normalize layout/OCR spacing from the published HTML before comparison."""
    return re.sub(r"[^0-9a-zа-яё]+", "", value.casefold())


def _verification_status(word_text: str, web_text: str) -> str:
    similarity = SequenceMatcher(None, _comparison_text(word_text), _comparison_text(web_text)).ratio()
    return "confirmed_by_web" if similarity >= 0.72 else "web_text_differs"


def build(docx_path: Path, output_path: Path, html_path: Path | None = None) -> int:
    primary = parse_docx(docx_path)
    chunks: list[Chunk] = list(primary)
    primary_paragraphs = {chunk.paragraph for chunk in primary if chunk.paragraph}
    if html_path and html_path.exists():
        web_chunks = parse_html(html_path)
        web_by_paragraph = {chunk.paragraph: chunk for chunk in web_chunks if chunk.paragraph}
        verified_primary: list[Chunk] = []
        for chunk in primary:
            web_match = web_by_paragraph.get(chunk.paragraph)
            if web_match:
                verified_primary.append(chunk.model_copy(update={
                    "verification_status": _verification_status(chunk.text, web_match.text),
                    "verification_url": web_match.source_url,
                }))
            else:
                verified_primary.append(chunk)
        # Word is authoritative. HTML is a fallback only for a numbered provision
        # absent from the Word file; it never replaces Word text.
        chunks = verified_primary
        chunks.extend(chunk for chunk in web_chunks if chunk.paragraph and chunk.paragraph not in primary_paragraphs)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps([chunk.model_dump() for chunk in chunks], ensure_ascii=False, indent=2), encoding="utf-8")
    return len(chunks)
