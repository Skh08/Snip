"""Low-cost end-to-end checks for a running local chatbot container."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

BASE_URL = "http://127.0.0.1:8000"
EVALUATION_CASES = Path(__file__).resolve().parents[1] / "tests" / "evaluation_cases.json"


def request(path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload else None
    headers = {"Content-Type": "application/json"} if data else {}
    with urlopen(Request(f"{BASE_URL}{path}", data=data, headers=headers), timeout=90) as response:  # nosec B310
        return json.loads(response.read())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    health = request("/health")
    require(health["status"] == "ok", "health endpoint is not ready")
    require(health["indexed_chunks"] > 0, "knowledge base has no chunks")
    require(health["secondary_source"]["local_copy_available"], "secondary HTML source was not downloaded")

    non_georgian = request("/chat", {"query": "What are the requirements?"})
    require(not non_georgian["grounded"], "non-Georgian question must not reach the model")
    require(not non_georgian["sources"], "non-Georgian question must have no sources")
    print("PASS: health, source availability, and Georgian-only input guard")

    if "--live" not in sys.argv:
        return

    cases = json.loads(EVALUATION_CASES.read_text(encoding="utf-8"))
    for case in cases:
        response = request("/chat", {"query": case["question"]})
        labels = [item["chunk"]["source_label"] for item in response["sources"]]
        require(response["grounded"], f"not grounded: {case['question']}")
        require(case["expected_source"] in labels, f"wrong source for {case['question']}: {labels}")
        for expected_text in case["expected_answer_terms"]:
            require(expected_text in response["answer"], f"missing expected wording for {case['question']}: {response['answer']}")
        print(f"PASS: {case['expected_source']} — {response['answer']}")

    ambiguous = request("/chat", {"query": "საბავშვო ბაღებში გაზი შეიძლება?"})
    require(not ambiguous["grounded"], "ambiguous kindergarten question must ask for clarification")
    require(not ambiguous["sources"], "clarification must not show a guessed source")
    require("დააზუსტეთ" in ambiguous["answer"], "clarification text is missing")
    print("PASS: ambiguous kindergarten question requests clarification")

    orientation = request("/chat", {"query": "რა დოკუმენტია ეს?"})
    require(not orientation["grounded"], "document orientation must not invoke RAG")
    require(not orientation["sources"], "document orientation must not show a source")
    require("გაზმომარაგების" in orientation["answer"], "document orientation answer is missing")
    print("PASS: document orientation is answered directly")


if __name__ == "__main__":
    main()
