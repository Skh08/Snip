"""Compare vector-only and hybrid retrieval against the checked evaluation set."""
from __future__ import annotations

import json
from pathlib import Path

from app.search import load_chunks
from app.semantic import semantic_search, vector_search

BASE_DIR = Path(__file__).resolve().parents[1]
CASES_PATH = BASE_DIR / "tests" / "evaluation_cases.json"
KNOWLEDGE_BASE = BASE_DIR / "data" / "knowledge_base.json"
EMBEDDINGS = BASE_DIR / "data" / "embeddings.json"


def _has_source(hits, expected: str) -> bool:
    return any(hit.chunk.source_label == expected for hit in hits)


def main() -> None:
    chunks = load_chunks(KNOWLEDGE_BASE)
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    vector_correct = 0
    hybrid_correct = 0
    for case in cases:
        vector_hits = vector_search(case["question"], chunks, EMBEDDINGS, 8)
        hybrid_hits = semantic_search(case["question"], chunks, EMBEDDINGS, 8)
        vector_ok = _has_source(vector_hits, case["expected_source"])
        hybrid_ok = _has_source(hybrid_hits, case["expected_source"])
        vector_correct += vector_ok
        hybrid_correct += hybrid_ok
        print(f"{case['expected_source']}: vector={vector_ok}; hybrid={hybrid_ok}")
    print(f"Vector-only: {vector_correct}/{len(cases)}")
    print(f"Hybrid: {hybrid_correct}/{len(cases)}")
    if hybrid_correct < vector_correct:
        raise SystemExit("Hybrid retrieval regressed; do not deploy it.")


if __name__ == "__main__":
    main()
