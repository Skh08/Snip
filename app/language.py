"""Language guard for a Georgian-language public chatbot."""
from __future__ import annotations

import re

GEORGIAN_LETTER = re.compile(r"[\u10D0-\u10FF]")
KINDERGARTEN_RE = re.compile(r"საბავშვო\s*ბაღ|ბავშვთა\s*ბაღ", re.IGNORECASE)
ROUTING_CONTEXT_RE = re.compile(r"გაზსადენ|მილ|კედელ|ტრანზიტ|მოწყობილ|ქურა|წნევ|გატარ", re.IGNORECASE)


def is_georgian_question(value: str) -> bool:
    """Accept questions containing Georgian script; numbers and punctuation are allowed."""
    return bool(GEORGIAN_LETTER.search(value))


def needs_clarification(value: str) -> bool:
    """Avoid presenting one narrow rule as a general kindergarten gas decision."""
    return bool(
        KINDERGARTEN_RE.search(value)
        and "შეიძლება" in value
        and not ROUTING_CONTEXT_RE.search(value)
    )
