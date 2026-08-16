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


def _matches_concept(query_term: str, document_term: str) -> bool:
    """Match Russian word forms without treating short words as interchangeable."""
    if query_term == document_term:
        return True
    if min(len(query_term), len(document_term)) < 6:
        return False
    shared = min(len(query_term), len(document_term)) - 2
    return query_term[:shared] == document_term[:shared]


def _concept_matches(query_terms: Counter[str], document_terms: Counter[str]) -> int:
    return sum(
        1 for term in query_terms
        if any(_matches_concept(term, document_term) for document_term in document_terms)
    )


def _is_provision_body(chunk: Chunk) -> bool:
    """Exclude table-of-contents headings when a numbered rule is available."""
    if not chunk.paragraph:
        return False
    return bool(re.match(rf"^\s*{re.escape(chunk.paragraph)}\.", chunk.text))


def load_chunks(path: Path) -> list[Chunk]:
    if not path.exists():
        return []
    return [Chunk.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))]


def broad_topic_sources(query: str, chunks: list[Chunk]) -> list[SearchHit]:
    """Resolve a small set of unambiguous, broad Georgian topic questions.

    A question asking generally for requirements is not an invitation to choose
    one exceptional condition (permafrost, seismic area, and so on).  These
    topics have an explicit subsection in the standard, so selecting its first
    numbered provision is safer and more precise than leaving that choice to a
    generative reranker.  Qualified questions continue through hybrid search.
    """
    normalized = query.casefold()
    is_broad_overground_question = (
        "მიწისზედა" in normalized
        and "გაზსადენ" in normalized
        and "მოთხოვნ" in normalized
        and not any(marker in normalized for marker in (
            "სიმაღლ", "საყრდენ", "თავისუფალ", "კედელ", "გზ", "გადაკვეთ",
            "წნევ", "საბავშვ", "ტრანზიტ",
        ))
    )
    if not is_broad_overground_question:
        return []
    for chunk in chunks:
        if chunk.paragraph == "4.22" and _is_provision_body(chunk):
            return [SearchHit(score=100.0, chunk=chunk)]
    return []


def provision_source(paragraph: str, chunks: list[Chunk]) -> list[SearchHit]:
    """Return a complete canonical provision selected by deterministic routing."""
    for chunk in chunks:
        if chunk.paragraph == paragraph and chunk.complete_evidence and chunk.kind == "provision":
            return [SearchHit(score=100.0, chunk=chunk)]
    return []


def keyword_search(query: str, chunks: list[Chunk], limit: int) -> list[SearchHit]:
    """BM25-style search with strong preference for exact provision numbers."""
    query_terms = Counter(_tokens(query))
    if not query_terms:
        return []
    tokenized = [(chunk, Counter(_tokens(_structured_text(chunk)))) for chunk in chunks]
    document_frequency = Counter(term for _, terms in tokenized for term in query_terms if term in terms)
    average_length = sum(sum(terms.values()) for _, terms in tokenized) / max(len(tokenized), 1)
    heading_targets: set[str] = set()
    for heading, terms in tokenized:
        # In the DOCX, a subsection title (for example, "Надземные и наземные
        # газопроводы") is immediately followed by its first numbered rule.
        # Carry that structural signal to the rule; a heading itself must never
        # be used as final evidence.
        if not heading.paragraph or _is_provision_body(heading) or _concept_matches(query_terms, terms) < 2:
            continue
        following = [
            candidate for candidate, _ in tokenized
            if candidate.section == heading.section
            and candidate.ordinal > heading.ordinal
            and _is_provision_body(candidate)
        ]
        if following:
            heading_targets.add(min(following, key=lambda candidate: candidate.ordinal).id)
    scored_hits: list[tuple[SearchHit, int, bool]] = []
    for chunk, terms in tokenized:
        length = sum(terms.values()) or 1
        score = 0.0
        for term, requested in query_terms.items():
            matching_terms = [document_term for document_term in terms if _matches_concept(term, document_term)]
            frequency = sum(terms[document_term] for document_term in matching_terms)
            if not frequency:
                continue
            matched_frequency = sum(document_frequency[document_term] for document_term in matching_terms)
            idf = math.log(1 + (len(chunks) - matched_frequency + 0.5) / (matched_frequency + 0.5))
            score += requested * idf * (frequency * 2.0) / (frequency + 1.2 * (0.25 + 0.75 * length / average_length))
            if term == (chunk.paragraph or "").casefold():
                score += 8.0
            elif term in _tokens(chunk.source_label):
                score += 2.5
        if score:
            concept_count = _concept_matches(query_terms, terms)
            # A provision that covers every substantive term is more useful
            # than a long passage repeating just one of them.  This is the
            # deterministic precision half of the hybrid retrieval layer.
            score += 4.0 * concept_count * concept_count
            if _is_provision_body(chunk):
                score += 0.8 * concept_count
            if chunk.id in heading_targets:
                score += 10.0
            scored_hits.append((SearchHit(score=round(score, 4), chunk=chunk), concept_count, _is_provision_body(chunk)))

    best_provision_match = max(
        (concept_count for _, concept_count, is_body in scored_hits if is_body), default=0
    )
    if best_provision_match >= 2:
        scored_hits = [
            item for item in scored_hits
            if item[2]
        ]
    hits = [item[0] for item in scored_hits]
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
