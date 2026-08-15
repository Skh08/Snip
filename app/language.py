"""Language guard for a Georgian-language public chatbot."""
from __future__ import annotations

import re

GEORGIAN_LETTER = re.compile(r"[\u10D0-\u10FF]")


def is_georgian_question(value: str) -> bool:
    """Accept questions containing Georgian script; numbers and punctuation are allowed."""
    return bool(GEORGIAN_LETTER.search(value))
