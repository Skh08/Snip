"""Deterministic guards between retrieval and answer generation."""
from __future__ import annotations

from .models import SearchHit


def usable_evidence(sources: list[SearchHit]) -> bool:
    """Allow only complete canonical rules or tables into the answer model."""
    if not sources:
        return False
    labels: set[str] = set()
    for hit in sources:
        chunk = hit.chunk
        if not chunk.complete_evidence or chunk.kind not in {"provision", "table"}:
            return False
        if not chunk.text.strip() or chunk.source_label in labels:
            return False
        labels.add(chunk.source_label)
    return True
