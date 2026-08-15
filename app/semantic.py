"""Multilingual retrieval and grounded answer generation through OpenAI."""
from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

from openai import OpenAI

from .models import Chunk, SearchHit

EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-5-mini")
MAX_OUTPUT_TOKENS = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "600"))
FOREIGN_LETTERS = re.compile(r"[A-Za-zА-Яа-яЁё]")
FORBIDDEN_GEORGIAN_OUTPUT = (
    "მთელყოფილად", "საბითუმო", "საქლიმატო წერტილი", "ნაძარცავი", "ტუფი",
    "მეთოდი −45", "მეთოდი -45",
)

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
            input=[f"{chunk.source_label}\n{chunk.text}" for chunk in batch],
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


def semantic_search(query: str, chunks: list[Chunk], embeddings_path: Path, limit: int) -> list[SearchHit]:
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
    return [SearchHit(score=round(score, 3), chunk=chunk) for score, chunk in ranked[:limit]]


def select_relevant_sources(question: str, candidates: list[SearchHit], limit: int = 3) -> list[SearchHit]:
    """Rerank candidates so unrelated nearby provisions never reach the answer prompt."""
    candidate_text = "\n\n".join(
        f"ID={item.chunk.id}\nSOURCE={item.chunk.source_label}\nTEXT={item.chunk.text}"
        for item in candidates
    )
    response = _client().responses.create(
        model=CHAT_MODEL,
        reasoning={"effort": "minimal"},
        max_output_tokens=200,
        instructions=("You are a strict evidence selector for a Russian technical standard. "
                      "Given a Georgian user question and candidate passages, choose only passages that directly answer it. "
                      "Do not include general or merely related provisions. Choose one passage when one is sufficient. "
                      f"Return only a JSON array of up to {limit} exact ID strings, with no Markdown or explanation."),
        input=f"Question: {question}\n\nCandidates:\n{candidate_text}",
    )
    raw = response.output_text.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        chosen_ids = json.loads(raw)
    except json.JSONDecodeError:
        return candidates[:1]
    if not isinstance(chosen_ids, list):
        return candidates[:1]
    selected = [item for item in candidates if item.chunk.id in chosen_ids][:limit]
    return selected or candidates[:1]


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


def polish_georgian_answer(draft: str) -> str:
    """Enforce the glossary and answer shape without changing cited facts."""
    response = _client().responses.create(
        model=CHAT_MODEL,
        reasoning={"effort": "minimal"},
        max_output_tokens=MAX_OUTPUT_TOKENS,
        instructions=("You are the final Georgian technical-language editor for a safety standard. "
                      "Rewrite the draft only to make it grammatical, precise, and natural Georgian. "
                      "Do not add, remove, infer, or change any technical fact, number, unit, condition, or scope. "
                      "Return exactly one short paragraph of one to three sentences, in Georgian only. "
                      "Do not include headings, sources, labels, Markdown, or commentary.\n\n"
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


# Re-declare the public answer function after the language editor so the response
# pipeline is always evidence generation followed by terminology enforcement.
def answer_question(question: str, sources: list[SearchHit]) -> str:
    evidence = "\n\n".join(f"[{item.chunk.source_label}]\n{item.chunk.text}" for item in sources)
    response = _client().responses.create(
        model=CHAT_MODEL,
        reasoning={"effort": "minimal"},
        max_output_tokens=MAX_OUTPUT_TOKENS,
        instructions=("Answer only from the supplied SNIP evidence. Write in Georgian only. "
                      "Return exactly one short, clear professional paragraph of one to three sentences. "
                      "Do not add a heading, a source line, labels, Markdown, Russian words, or facts not in evidence. "
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
    polished = polish_georgian_answer(answer)
    if _valid_final_answer(polished):
        return polished
    # A second correction is used only when the first language pass produced
    # malformed mixed-script text, keeping ordinary requests economical.
    corrected = polish_georgian_answer(
        "The previous draft violated the Georgian-only terminology rules. "
        "Correct it without changing any facts: " + polished
    )
    if not _valid_final_answer(corrected):
        raise RuntimeError("ქართული ტექნიკური პასუხის ხარისხის შემოწმება ვერ გაიარა. სცადეთ კითხვა უფრო კონკრეტულად.")
    return corrected
