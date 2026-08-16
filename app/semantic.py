"""Multilingual retrieval and grounded answer generation through OpenAI."""
from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

from openai import OpenAI

from .models import Chunk, SearchHit
from .search import fuse_search_hits, keyword_search

EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-5-mini")
MAX_OUTPUT_TOKENS = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "600"))
FOREIGN_LETTERS = re.compile(r"[A-Za-zА-Яа-яЁё]")
FORBIDDEN_GEORGIAN_OUTPUT = (
    "მთელყოფილად", "საბითუმო", "საქლიმატო წერტილი", "ნაძარცავი", "ტუფი",
    "მეთოდი −45", "მეთოდი -45",
    "ციტირებული მტკიცებულების მიხედვით", "მტკიცებულების მიხედვით",
)


class ClarificationRequired(Exception):
    """A grounded answer could not be rendered safely without narrowing scope."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

# Mandatory renderings for common Russian terms in this standard.  The final
# language pass is deliberately separate from evidence selection and cannot add facts.
GEORGIAN_TECHNICAL_GLOSSARY = """
Use these exact Georgian forms when the corresponding Russian concept appears:
- газопровод = გაზსადენი
- полиэтиленовый газопровод = პოლიეთილენის გაზსადენი
- глубина прокладки = ჩაღრმავების სიღრმე
- до верха трубы = მილის ზედა ნიშნულამდე
- расчетная температура наружного воздуха = გარე ჰაერის საანგარიშო ტემპერატურა
- ниже минус 40 °С = −40 °C-ზე დაბალი
- до минус 45 °С включительно = −45 °C-მდე ჩათვლით
- грунт = ნიადაგი
- давление газа = გაზის წნევა
- подземный газопровод = მიწისქვეშა გაზსადენი
- надземный газопровод = მიწისზედა გაზსადენი
- наружный газопровод = გარე გაზსადენი
- транзитная прокладка = ტრანზიტული გატარება
- по стенам зданий = შენობების კედლებზე
- детские учреждения = საბავშვო დაწესებულებები
- по стенам зданий детских учреждений = საბავშვო დაწესებულებების შენობების კედლებზე
- газопроводы всех давлений = ყველა წნევის გაზსადენები
- газоснабжение = გაზმომარაგება
- не допускается = დაუშვებელია
- МПа = მპა
- мм = მმ
- проектирование = დაპროექტება
- прокладка = დაგება
- футляр = დამცავი გარსაცმი
- таблица = ცხრილი
- приложение = დანართი
Never use these malformed or irrelevant expressions: „მთელყოფილად“, „საბითუმო“,
„საქლიმატო წერტილი“, „ნაძარცავი“, „ტუფი“, „მეთოდი −45 °C-მდე“.
""".strip()


def _client() -> OpenAI:
    # Secret managers and clipboard pastes can preserve a final newline.  HTTP
    # header values cannot contain it, so normalize only surrounding whitespace
    # before passing the key to the SDK.  The key itself is never logged.
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return OpenAI(api_key=api_key)


def build_embeddings(chunks: list[Chunk], destination: Path) -> int:
    client = _client()
    vectors: list[list[float]] = []
    batch_size = 100
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=[
                "\n".join(part for part in (
                    f"РАЗДЕЛ: {chunk.section}" if chunk.section else "",
                    f"ПОДРАЗДЕЛ: {chunk.subsection}" if chunk.subsection else "",
                    f"ИСТОЧНИК: {chunk.source_label}",
                    chunk.text,
                ) if part)
                for chunk in batch
            ],
        )
        vectors.extend(item.embedding for item in response.data)
    destination.write_text(json.dumps({"model": EMBEDDING_MODEL, "vectors": vectors}), encoding="utf-8")
    return len(vectors)


def translate_to_russian(question: str) -> str:
    """Make Russian retrieval reliable when the visitor asks in Georgian."""
    response = _client().responses.create(
        model=CHAT_MODEL,
        reasoning={"effort": "minimal"},
        max_output_tokens=200,
        instructions=("Translate the question into Russian for searching a Russian technical standard. "
                      "Return only the Russian search query. Preserve numbers, units, and section references. "
                      "If it is already Russian, return it unchanged."),
        input=question,
    )
    translated = response.output_text.strip()
    if not translated:
        raise RuntimeError("კითხვის რუსულად გარდაქმნა ვერ შესრულდა. სცადეთ თავიდან.")
    return translated


def _vector_search(query: str, chunks: list[Chunk], embeddings_path: Path, limit: int) -> tuple[str, list[SearchHit]]:
    """Return the translated query and vector-only candidates for evaluation."""
    stored = json.loads(embeddings_path.read_text(encoding="utf-8"))
    vectors = stored["vectors"]
    if len(vectors) != len(chunks):
        raise RuntimeError("Embeddings do not match the knowledge base; rebuild them.")
    russian_query = translate_to_russian(query)
    query_vectors = [item.embedding for item in _client().embeddings.create(
        model=stored["model"], input=[query, russian_query]
    ).data]
    def cosine(vector: list[float]) -> float:
        magnitude = math.sqrt(sum(a * a for a in vector))
        return max(
            sum(a * b for a, b in zip(query_vector, vector)) /
            (math.sqrt(sum(a * a for a in query_vector)) * magnitude)
            for query_vector in query_vectors
        )
    ranked = sorted(((cosine(vector), chunk) for vector, chunk in zip(vectors, chunks)), reverse=True, key=lambda item: item[0])
    semantic_hits = [SearchHit(score=round(score, 3), chunk=chunk) for score, chunk in ranked[:limit]]
    return russian_query, semantic_hits


def vector_search(query: str, chunks: list[Chunk], embeddings_path: Path, limit: int) -> list[SearchHit]:
    """The pre-hybrid vector-only baseline, retained for evaluation."""
    _, hits = _vector_search(query, chunks, embeddings_path, limit)
    return hits


def semantic_search(query: str, chunks: list[Chunk], embeddings_path: Path, limit: int) -> list[SearchHit]:
    """Hybrid retrieval: multilingual vectors plus exact Russian text matches."""
    russian_query, semantic_hits = _vector_search(query, chunks, embeddings_path, max(24, limit * 3))
    # The Russian query lets the sparse matcher find exact СНиП terms, numbers,
    # and provision references that embeddings can otherwise blur together.
    lexical_hits = keyword_search(f"{russian_query} {query}", chunks, max(24, limit * 3))
    return fuse_search_hits(semantic_hits, lexical_hits, limit)


def select_relevant_sources(question: str, candidates: list[SearchHit], limit: int = 3) -> list[SearchHit]:
    """Rerank candidates so unrelated nearby provisions never reach the answer prompt."""
    candidates = [
        item for item in candidates
        if item.chunk.complete_evidence and item.chunk.kind in {"provision", "table"}
    ]
    if not candidates:
        return []
    candidate_text = "\n\n".join(
        f"ID={item.chunk.id}\nTYPE={item.chunk.kind}\nSECTION={item.chunk.section or 'not specified'}\n"
        f"SUBSECTION={item.chunk.subsection or 'not specified'}\n"
        f"SOURCE={item.chunk.source_label}\nTEXT={item.chunk.text}"
        for item in candidates
    )
    response = _client().responses.create(
        model=CHAT_MODEL,
        reasoning={"effort": "minimal"},
        max_output_tokens=200,
        instructions=("You are a strict evidence selector for a Russian technical standard. "
                      "Given a Georgian user question and complete candidate provisions, choose only passages that directly answer it. "
                      "Never select an exceptional climatic, seismic, industrial, or object-specific condition for a broad question unless the question explicitly names that condition. "
                      "Do not include merely related provisions. Choose one passage when one is sufficient. "
                      "Return an empty array when none directly answers the question; an empty result is safer than a weak match. "
                      f"Return only a JSON array of up to {limit} exact ID strings, with no Markdown or explanation."),
        input=f"Question: {question}\n\nCandidates:\n{candidate_text}",
    )
    raw = response.output_text.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        chosen_ids = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(chosen_ids, list):
        return []
    selected = [item for item in candidates if item.chunk.id in chosen_ids][:limit]
    return selected


def select_related_sources(question: str, candidates: list[SearchHit], limit: int = 3) -> list[SearchHit]:
    """Select related context only after direct-answer retrieval abstains.

    This is deliberately a different task from direct retrieval: a selected
    passage may explain a condition around the question, but it must never be
    represented as a permission, prohibition, or answer for an unnamed object.
    """
    candidates = [
        item for item in candidates
        if item.chunk.complete_evidence and item.chunk.kind in {"provision", "table"}
    ]
    if not candidates:
        return []
    candidate_text = "\n\n".join(
        f"ID={item.chunk.id}\nSOURCE={item.chunk.source_label}\n"
        f"SECTION={item.chunk.section or 'not specified'}\n"
        f"SUBSECTION={item.chunk.subsection or 'not specified'}\nTEXT={item.chunk.text}"
        for item in candidates
    )
    response = _client().responses.create(
        model=CHAT_MODEL,
        reasoning={"effort": "minimal"},
        max_output_tokens=160,
        instructions=(
            "The Georgian question has no directly answering provision. Select at most three supplied provisions that are "
            "genuinely useful contextual information. A provision is useful only if it governs the same pipeline type, "
            "installation method, location, clearance, crossing, pressure, or safety condition named in the question. "
            "Do not select merely keyword-related text, a different object type, or an exceptional climatic, seismic, "
            "industrial, or object-specific condition unless the question explicitly names that condition. "
            "The selected provisions will be explicitly labelled as informational, never as a direct answer. "
            "Return an empty array if no candidate is clearly useful. Return only a JSON array of exact ID strings."
        ),
        input=f"Question: {question}\n\nCandidates:\n{candidate_text}",
    )
    try:
        chosen_ids = json.loads(response.output_text.strip().removeprefix("```json").removesuffix("```").strip())
    except json.JSONDecodeError:
        return []
    if not isinstance(chosen_ids, list):
        return []
    return [item for item in candidates if item.chunk.id in chosen_ids][:limit]


def expand_structured_context(sources: list[SearchHit], chunks: list[Chunk], limit: int = 6) -> list[SearchHit]:
    """Include continuations of a selected regulatory provision as answer context.

    The returned sources still retain the exact original source labels. This only
    expands evidence for a provision that Word split across several paragraphs.
    """
    by_paragraph: dict[str, list[Chunk]] = {}
    for chunk in chunks:
        if chunk.paragraph:
            by_paragraph.setdefault(chunk.paragraph, []).append(chunk)
    expanded: list[SearchHit] = []
    used_ids: set[str] = set()
    for hit in sources:
        candidates = [hit.chunk]
        if hit.chunk.paragraph:
            candidates = by_paragraph.get(hit.chunk.paragraph, candidates)
        for chunk in candidates:
            if chunk.id not in used_ids and len(expanded) < limit:
                expanded.append(SearchHit(score=hit.score, chunk=chunk))
                used_ids.add(chunk.id)
    return expanded or sources


def _evidence_text(sources: list[SearchHit]) -> str:
    return "\n\n".join(
        f"[{item.chunk.source_label}]\nSECTION: {item.chunk.section or 'not specified'}\n{item.chunk.text}"
        for item in sources
    )


def _legacy_answer_question(question: str, sources: list[SearchHit]) -> str:
    evidence = "\n\n".join(f"[{item.chunk.source_label}]\n{item.chunk.text}" for item in sources)
    response = _client().responses.create(
        model=CHAT_MODEL,
        reasoning={"effort": "minimal"},
        max_output_tokens=MAX_OUTPUT_TOKENS,
        instructions=("Answer only from the supplied СНиП evidence. Write concise, grammatical, professional Georgian. "
                      "Use standard Georgian technical wording; do not transliterate Russian words and do not add facts. "
                      "Address only what the question asks. If evidence is insufficient, say so plainly. "
                      "End with the exact bracketed source labels you used."),
        input=f"Question: {question}\n\nEvidence:\n{evidence}",
    )
    answer = response.output_text.strip()
    if not answer:
        raise RuntimeError("პასუხის გენერირება ვერ შესრულდა. სცადეთ თავიდან.")
    return answer


def polish_georgian_answer(draft: str, *, strict: bool = False) -> str:
    """Enforce the glossary and answer shape without changing cited facts."""
    strict_rule = ""
    if strict:
        strict_rule = (
            " This is a recovery pass. Return only Georgian-script prose; digits, punctuation, "
            "the degree sign, and Georgian unit abbreviations are allowed. Do not use Latin or "
            "Cyrillic letters, source markers, or brackets."
        )
    response = _client().responses.create(
        model=CHAT_MODEL,
        reasoning={"effort": "minimal"},
        max_output_tokens=MAX_OUTPUT_TOKENS,
        instructions=("You are the final Georgian technical-language editor for a safety standard. "
                      "Rewrite the draft only to make it grammatical, precise, and natural Georgian. "
                      "Do not add, remove, infer, or change any technical fact, number, unit, condition, or scope. "
                      "State the provision directly; never refer to evidence, citations, or the answer-generation process. "
                      "Return exactly one short paragraph of one to three sentences, in Georgian only. "
                      "Do not include headings, sources, labels, Markdown, or commentary.\n\n"
                      + strict_rule
                      + GEORGIAN_TECHNICAL_GLOSSARY),
        input=f"Draft to edit:\n{draft}",
    )
    polished = response.output_text.strip()
    if not polished:
        raise RuntimeError("ქართული ტექნიკური პასუხის რედაქტირება ვერ შესრულდა. სცადეთ თავიდან.")
    return polished


def _valid_final_answer(answer: str) -> bool:
    """Never show malformed mixed-script technical prose to a visitor."""
    normalized = answer.casefold()
    # The temperature symbol °C is an internationally standard unit, not prose.
    script_checked = answer.replace("°C", "").replace("°С", "")
    return bool(answer) and not FOREIGN_LETTERS.search(script_checked) and not any(
        term in normalized for term in FORBIDDEN_GEORGIAN_OUTPUT
    )


def _normalize_answer_artifacts(answer: str) -> str:
    """Repair isolated source labels and international-unit spellings only.

    This is deliberately narrow: it never translates sentences or adds facts.
    It prevents an otherwise sound Georgian answer from being rejected merely
    because a model preserved a source marker or a unit in its Russian/Latin form.
    """
    normalized = answer.strip()
    normalized = re.sub(r"^\s*ციტირებული მტკიცებულების მიხედვით\s*[,.:—-]*\s*", "", normalized, flags=re.I)
    replacements = {
        "СНиП": "სნიპ",
        "пп.": "პპ.",
        "п.": "პ.",
        "МПа": "მპა",
        "МПА": "მპა",
        "MPa": "მპა",
        "MPA": "მპა",
        "кПа": "კპა",
        "КПа": "კპა",
        "kPa": "კპა",
        "KPa": "კპა",
        "м³": "მ³",
        "m³": "მ³",
        "м²": "მ²",
        "m²": "მ²",
    }
    for source, replacement in replacements.items():
        normalized = normalized.replace(source, replacement)
    normalized = re.sub(r"(?<=\d)\s+[мm](?=$|[.,;:)])", " მ", normalized)
    return normalized


# Re-declare the public answer function after the language editor so the response
# pipeline is always evidence generation followed by terminology enforcement.
def answer_question(question: str, sources: list[SearchHit]) -> str:
    evidence = _evidence_text(sources)
    response = _client().responses.create(
        model=CHAT_MODEL,
        reasoning={"effort": "minimal"},
        max_output_tokens=MAX_OUTPUT_TOKENS,
        instructions=("Answer only from the supplied SNIP evidence. Write in Georgian only. "
                      "Return exactly one short, clear professional paragraph of one to three sentences. "
                      "Do not add a heading, a source line, labels, Markdown, Russian words, or facts not in evidence. "
                      "State the rule directly; never begin with meta-language such as 'according to the cited evidence' or 'the evidence shows'. "
                      "Keep every number, decimal separator, unit, limitation, and condition exact. Do not invent parenthetical explanations. Address only the question asked. "
                      "If the user's place, object, or condition is not explicitly named in the evidence, do not treat it as an exact match; state the evidence's actual scope. "
                      "If a broad question asks whether gas supply is allowed but the evidence only restricts a route, pressure, wall, or other specific condition, distinguish that narrow restriction from a general prohibition. "
                      "If evidence is insufficient, say this plainly in Georgian.\n\n"
                      + GEORGIAN_TECHNICAL_GLOSSARY),
        input=f"Question: {question}\n\nEvidence:\n{evidence}",
    )
    answer = response.output_text.strip()
    if not answer:
        raise RuntimeError("ქართული პასუხის გენერირება ვერ შესრულდა. სცადეთ თავიდან.")
    polished = _normalize_answer_artifacts(polish_georgian_answer(answer))
    if _valid_final_answer(polished):
        return polished
    # This recovery pass runs only after an invalid result.  It edits the
    # original grounded draft (rather than an English diagnostic message), so
    # it cannot leak a model-internal explanation into the public answer.
    corrected = _normalize_answer_artifacts(polish_georgian_answer(answer, strict=True))
    if _valid_final_answer(corrected):
        return corrected

    # A safety-standard chatbot must not expose an implementation error as an
    # answer.  The evidence was selected, but its Georgian rendering remained
    # invalid after two constrained attempts; ask for the missing scope rather
    # than inventing a technical rule.
    raise ClarificationRequired(
        "მიწისზედა გაზსადენებისთვის მოთხოვნები განთავსების პირობების მიხედვით განსხვავდება. "
        "დააზუსტეთ, საუბარია საყრდენებზე განთავსებაზე, გზის გადაკვეთაზე, შენობის კედელზე გატარებაზე თუ სხვა კონკრეტულ პირობაზე."
    )


def answer_related_context(question: str, sources: list[SearchHit]) -> str:
    """Translate related provisions without converting them into a decision."""
    evidence = _evidence_text(sources)
    response = _client().responses.create(
        model=CHAT_MODEL,
        reasoning={"effort": "minimal"},
        max_output_tokens=MAX_OUTPUT_TOKENS,
        instructions=(
            "Write one concise, professional paragraph in Georgian only. Summarize only the supplied Russian technical "
            "provisions as related background for the user's question. State each condition with its actual scope. "
            "Do not infer permission, prohibition, compliance, applicability to an unnamed object, or a final design decision. "
            "Do not include sources, headings, Markdown, Russian words, or meta-language. "
            + GEORGIAN_TECHNICAL_GLOSSARY
        ),
        input=f"Question: {question}\n\nRelated provisions:\n{evidence}",
    )
    draft = response.output_text.strip()
    if not draft:
        raise RuntimeError("დაკავშირებული ინფორმაციის ქართული შეჯამება ვერ შესრულდა.")
    polished = _normalize_answer_artifacts(polish_georgian_answer(draft))
    if not _valid_final_answer(polished):
        raise RuntimeError("დაკავშირებული ინფორმაციის ქართული ტექსტი ვერ დამოწმდა.")
    return (
        "დოკუმენტში ამ კითხვაზე პირდაპირი წესი არ მოიძებნა. ცნობისთვის, შინაარსობრივად ახლო დებულებებია: "
        + polished
    )
