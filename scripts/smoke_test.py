"""Low-cost end-to-end checks for a running local chatbot container."""
from __future__ import annotations

import json
import sys
from urllib.request import Request, urlopen

BASE_URL = "http://127.0.0.1:8000"


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

    cases = (
        ("რა არის პოლიეთილენის გაზსადენის ჩაღრმავების მინიმალური სიღრმე?", "п. 4.92", "1"),
        ("რა მოთხოვნაა თავისუფალ ტერიტორიაზე დაბალ საყრდენებზე მოწყობილი მიწისზედა გაზსადენისთვის?", "п. 4.28", "0,35"),
        ("საბავშვო ბაღებში ტრანზიტული გაზსადენის გატარება დასაშვებია?", "п. 4.22", "ტრანზიტ"),
    )
    for question, expected_source, expected_text in cases:
        response = request("/chat", {"query": question})
        labels = [item["chunk"]["source_label"] for item in response["sources"]]
        require(response["grounded"], f"not grounded: {question}")
        require(expected_source in labels, f"wrong source for {question}: {labels}")
        require(expected_text in response["answer"], f"missing expected wording for {question}: {response['answer']}")
        print(f"PASS: {expected_source} — {response['answer']}")

    ambiguous = request("/chat", {"query": "საბავშვო ბაღებში გაზი შეიძლება?"})
    require(not ambiguous["grounded"], "ambiguous kindergarten question must ask for clarification")
    require(not ambiguous["sources"], "clarification must not show a guessed source")
    require("დააზუსტეთ" in ambiguous["answer"], "clarification text is missing")
    print("PASS: ambiguous kindergarten question requests clarification")


if __name__ == "__main__":
    main()
