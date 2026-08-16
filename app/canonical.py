"""Create complete, provision-level evidence records from visual DOCX chunks."""
from __future__ import annotations

import re
from collections import OrderedDict

from .models import Chunk

_NUMBERED_BODY = re.compile(r"^\s*(\d+(?:\.\d+)+)\.")
_TABLE_LABEL = re.compile(r"^Таблица\s+\d+", re.IGNORECASE)


def _is_subsection_heading(chunk: Chunk) -> bool:
    """Identify a visual subsection title that must not become rule evidence."""
    text = chunk.text.strip()
    if _NUMBERED_BODY.match(text) or _TABLE_LABEL.match(text):
        return False
    if len(text) < 4 or len(text) > 120 or text[-1:] in ".;:!?":
        return False
    # A title is usually a short capitalized phrase.  This also catches a title
    # inherited by the legacy parser as a continuation of the preceding rule.
    return bool(re.match(r"^[А-ЯЁA-Z][^\n]*$", text))


def canonicalize(chunks: list[Chunk]) -> list[Chunk]:
    """Merge continuations into one complete source record per provision.

    Raw Word paragraphs are presentation fragments.  A regulatory answer must
    instead receive the full numbered provision, never its title or one
    arbitrary continuation.  Tables remain individual records until a table
    parser supplies stronger row metadata.
    """
    provisions: OrderedDict[str, dict] = OrderedDict()
    tables: OrderedDict[tuple[str | None, str], dict] = OrderedDict()
    subsection: str | None = None

    for raw in sorted(chunks, key=lambda item: item.ordinal):
        if _is_subsection_heading(raw):
            subsection = raw.text.strip()
            continue

        if raw.paragraph:
            entry = provisions.setdefault(raw.paragraph, {
                "first": raw,
                "text": [],
                "subsection": subsection,
                "fragments": [],
            })
            entry["text"].append(raw.text)
            entry["fragments"].append(raw)
            continue

        if raw.kind == "table_text" or _TABLE_LABEL.match(raw.source_label):
            key = (raw.section, raw.source_label)
            entry = tables.setdefault(key, {"first": raw, "text": [], "fragments": []})
            entry["text"].append(raw.text)
            entry["fragments"].append(raw)

    canonical: list[Chunk] = []
    for paragraph, entry in provisions.items():
        first: Chunk = entry["first"]
        text = "\n".join(dict.fromkeys(entry["text"])).strip()
        canonical.append(first.model_copy(update={
            "id": f"provision-{paragraph}",
            "text": text,
            "source_label": f"п. {paragraph}",
            "subsection": entry["subsection"],
            "kind": "provision",
            "fragment_count": len(entry["fragments"]),
            "complete_evidence": True,
        }))

    for (_, label), entry in tables.items():
        first = entry["first"]
        text = "\n".join(dict.fromkeys(entry["text"])).strip()
        canonical.append(first.model_copy(update={
            "id": f"table-{first.ordinal}",
            "text": text,
            "source_label": label,
            "subsection": subsection,
            "kind": "table",
            "fragment_count": len(entry["fragments"]),
            "complete_evidence": True,
        }))

    return sorted(canonical, key=lambda item: item.ordinal)
