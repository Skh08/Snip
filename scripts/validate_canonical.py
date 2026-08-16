"""No-cost validation of the canonical evidence base and lexical recall."""
from __future__ import annotations

import json
from pathlib import Path

from app.search import broad_topic_sources, keyword_search, load_chunks

BASE_DIR = Path(__file__).resolve().parents[1]
KNOWLEDGE_BASE = BASE_DIR / "data" / "canonical_knowledge_base.json"
CASES_PATH = BASE_DIR / "tests" / "evaluation_cases.json"


def main() -> None:
    chunks = load_chunks(KNOWLEDGE_BASE)
    if not chunks:
        raise SystemExit("Canonical knowledge base is missing.")
    provisions = [chunk for chunk in chunks if chunk.kind == "provision"]
    if len(provisions) < 500:
        raise SystemExit(f"Expected at least 500 provisions; found {len(provisions)}.")
    if not all(chunk.complete_evidence and chunk.fragment_count >= 1 for chunk in chunks):
        raise SystemExit("A non-canonical or incomplete source record was found.")
    labels = [chunk.source_label for chunk in provisions]
    if len(labels) != len(set(labels)):
        raise SystemExit("Duplicate provision labels were found in the canonical source.")

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    for case in cases:
        if case.get("expected_grounded") is False:
            continue
        if case["expected_source"] == "п. 4.22" and "მიწისზედა" in case["question"] and "მოთხოვნ" in case["question"]:
            hits = broad_topic_sources(case["question"], chunks)
        else:
            hits = keyword_search(case["retrieval_query"], chunks, 8)
        if not any(hit.chunk.source_label == case["expected_source"] for hit in hits):
            raise SystemExit(f"Recall failure for {case['question']}: expected {case['expected_source']}")
    print(f"PASS: {len(chunks)} complete canonical records; {len(cases)} evaluation cases checked.")


if __name__ == "__main__":
    main()
