"""Language guard for a Georgian-language public chatbot."""
from __future__ import annotations

import re

GEORGIAN_LETTER = re.compile(r"[\u10D0-\u10FF]")
KINDERGARTEN_RE = re.compile(r"საბავშვო\s*ბაღ|ბავშვთა\s*ბაღ", re.IGNORECASE)
ROUTING_CONTEXT_RE = re.compile(r"გაზსადენ|მილ|კედელ|ტრანზიტ|მოწყობილ|ქურა|წნევ|გატარ", re.IGNORECASE)
ABOUT_DOCUMENT_RE = re.compile(
    r"(?:რა\s+დოკუმენტია\s*(?:ეს)?|ეს\s+რა\s+დოკუმენტია|"
    r"(?:რას\s+ეხება|რის\s+შესახებაა)\s*(?:ეს|კითხვა(?:[-\s]*პასუხი)?|ჩატბოტი|დოკუმენტი)?)\s*[?!.]*$",
    re.IGNORECASE,
)

ABOUT_DOCUMENT_ANSWER = (
    "ეს არის СНиП 2.04.08-87 — გაზმომარაგების ნორმატიული დოკუმენტი. "
    "ჩატბოტი პასუხობს ამ დოკუმენტში მოცემულ მოთხოვნებზე: გაზსადენების დაგებაზე, "
    "გაზის წნევაზე, უსაფრთხოებაზე და გაზმომარაგების მოწყობილობებზე. "
    "კითხვა მოგვაწოდეთ ქართულად."
)


def is_georgian_question(value: str) -> bool:
    """Accept questions containing Georgian script; numbers and punctuation are allowed."""
    return bool(GEORGIAN_LETTER.search(value))


def about_document_answer(value: str) -> str | None:
    """Answer public app-orientation questions without running RAG or the API."""
    return ABOUT_DOCUMENT_ANSWER if ABOUT_DOCUMENT_RE.search(value) else None


def needs_clarification(value: str) -> bool:
    """Avoid presenting one narrow rule as a general kindergarten gas decision."""
    return bool(
        KINDERGARTEN_RE.search(value)
        and "შეიძლება" in value
        and not ROUTING_CONTEXT_RE.search(value)
    )
