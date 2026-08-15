"""Multilingual retrieval and grounded answer generation through OpenAI."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

from openai import OpenAI

from .models import Chunk, SearchHit

EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-5-mini")
MAX_OUTPUT_TOKENS = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "600"))


def _client() -> OpenAI:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return OpenAI()


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


def answer_question(question: str, sources: list[SearchHit]) -> str:
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
