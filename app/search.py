from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from .models import Chunk, SearchHit


def _tokens(value: str) -> list[str]:
    return re.findall(r"[\w.-]+", value.lower(), flags=re.UNICODE)


def load_chunks(path: Path) -> list[Chunk]:
    if not path.exists():
        return []
    return [Chunk.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))]


def search(query: str, chunks: list[Chunk], limit: int) -> list[SearchHit]:
    query_terms = Counter(_tokens(query))
    if not query_terms:
        return []
    hits = []
    for chunk in chunks:
        terms = Counter(_tokens(f"{chunk.source_label} {chunk.text}"))
        overlap = sum(min(count, terms[term]) for term, count in query_terms.items())
        if overlap:
            score = overlap / len(query_terms)
            hits.append(SearchHit(score=round(score, 3), chunk=chunk))
    return sorted(hits, key=lambda hit: (hit.score, -hit.chunk.ordinal), reverse=True)[:limit]
