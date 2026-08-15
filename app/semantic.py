"""Multilingual retrieval and grounded answer generation through OpenAI."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

from openai import OpenAI

from .models import Chunk, SearchHit

EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-5-mini")


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


def semantic_search(query: str, chunks: list[Chunk], embeddings_path: Path, limit: int) -> list[SearchHit]:
    stored = json.loads(embeddings_path.read_text(encoding="utf-8"))
    vectors = stored["vectors"]
    if len(vectors) != len(chunks):
        raise RuntimeError("Embeddings do not match the knowledge base; rebuild them.")
    query_vector = _client().embeddings.create(model=stored["model"], input=query).data[0].embedding
    def cosine(vector: list[float]) -> float:
        return sum(a * b for a, b in zip(query_vector, vector)) / (math.sqrt(sum(a * a for a in query_vector)) * math.sqrt(sum(b * b for b in vector)))
    ranked = sorted(((cosine(vector), chunk) for vector, chunk in zip(vectors, chunks)), reverse=True, key=lambda item: item[0])
    return [SearchHit(score=round(score, 3), chunk=chunk) for score, chunk in ranked[:limit]]


def answer_question(question: str, sources: list[SearchHit]) -> str:
    evidence = "\n\n".join(f"[{item.chunk.source_label}]\n{item.chunk.text}" for item in sources)
    response = _client().responses.create(
        model=CHAT_MODEL,
        instructions=("Answer only from the supplied СНиП evidence. Answer in the user's language. "
                      "If the evidence is insufficient, say so plainly. Do not invent requirements or sources. "
                      "End with the exact bracketed source labels you used."),
        input=f"Question: {question}\n\nEvidence:\n{evidence}",
    )
    return response.output_text
