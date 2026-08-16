"""Deterministic lexical and hybrid retrieval helpers."""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

from .models import Chunk, SearchHit


def _tokens(value: str) -> list[str]:
    """Keep provision numbers and decimal values as searchable terms."""
    return re.findall(r"[\w]+(?:[.,][\w]+)*", value.casefold(), flags=re.UNICODE)


def _structured_text(chunk: Chunk) -> str:
    return " ".join(part for part in (chunk.section, chunk.paragraph, chunk.source_label, chunk.text) if part)


def load_chunks(path: Path) -> list[Chunk]:
    if not path.exists():
        return []
    return [Chunk.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))]


def keyword_search(query: str, chunks: list[Chunk], limit: int) -> list[SearchHit]:
    """BM25-style search with strong preference for exact provision numbers."""
    query_terms = Counter(_tokens(query))
    if not query_terms:
        return []
    tokenized = [(chunk, Counter(_tokens(_structured_text(chunk)))) for chunk in chunks]
    document_frequency = Counter(term for _, terms in tokenized for term in query_terms if term in terms)
    average_length = sum(sum(terms.values()) for _, terms in tokenized) / max(len(tokenized), 1)
    hits: list[SearchHit] = []
    for chunk, terms in tokenized:
        length = sum(terms.values()) or 1
        score = 0.0
        for term, requested in query_terms.items():
            frequency = terms.get(term, 0)
            if not frequency:
                continue
            idf = math.log(1 + (len(chunks) - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5))
            score += requested * idf * (frequency * 2.0) / (frequency + 1.2 * (0.25 + 0.75 * length / average_length))
            if term == (chunk.paragraph or "").casefold():
                score += 8.0
            elif term in _tokens(chunk.source_label):
                score += 2.5
        if score:
            hits.append(SearchHit(score=round(score, 4), chunk=chunk))
    return sorted(hits, key=lambda hit: (hit.score, -hit.chunk.ordinal), reverse=True)[:limit]


def fuse_search_hits(semantic: list[SearchHit], keyword: list[SearchHit], limit: int) -> list[SearchHit]:
    """Fuse semantic recall with exact-text precision without another API call."""
    semantic_rank = {hit.chunk.id: index for index, hit in enumerate(semantic, start=1)}
    keyword_rank = {hit.chunk.id: index for index, hit in enumerate(keyword, start=1)}
    lookup = {hit.chunk.id: hit for hit in [*semantic, *keyword]}
    maximum_keyword_score = max((hit.score for hit in keyword), default=1.0)
    merged: list[SearchHit] = []
    for chunk_id, hit in lookup.items():
        score = 0.0
        if chunk_id in semantic_rank:
            score += 0.65 / (50 + semantic_rank[chunk_id])
        if chunk_id in keyword_rank:
            score += 0.35 / (50 + keyword_rank[chunk_id])
            score += 0.60 * (hit.score / maximum_keyword_score)
        merged.append(SearchHit(score=round(score * 100, 3), chunk=hit.chunk))
    return sorted(merged, key=lambda hit: (hit.score, -hit.chunk.ordinal), reverse=True)[:limit]


def search(query: str, chunks: list[Chunk], limit: int) -> list[SearchHit]:
    """Public deterministic search endpoint: exact and structural text matching."""
    return keyword_search(query, chunks, limit)
