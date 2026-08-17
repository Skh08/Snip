from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from openai import OpenAIError
from fastapi.staticfiles import StaticFiles

from .models import ChatResponse, SearchRequest, SearchHit
from .language import (
    about_document_answer,
    checked_rule_answer,
    is_georgian_question,
    needs_clarification,
    overground_compound_clarification,
    overground_crossing_answer,
    overground_overview_answer,
    parking_related_answer,
    wet_room_related_answer,
)
from .search import broad_topic_sources, load_chunks, provision_source, search
from .validation import usable_evidence
from .semantic import (
    ClarificationRequired,
    answer_question,
    answer_related_context,
    expand_structured_context,
    select_relevant_sources,
    select_related_sources,
    semantic_search,
)

BASE_DIR = Path(__file__).resolve().parents[1]
KNOWLEDGE_BASE = BASE_DIR / "data" / "canonical_knowledge_base.json"
EMBEDDINGS = BASE_DIR / "data" / "canonical_embeddings.json"
HTML_SOURCE = BASE_DIR / "data" / "snip_2.04.08-87.html"
app = FastAPI(title="СНиП Chatbot API", version="0.1.0")
STATIC_DIR = BASE_DIR / "static"


def related_context_response(query: str, candidates: list[SearchHit], chunks: list) -> ChatResponse | None:
    """Return explicitly labelled background only when direct retrieval abstained."""
    try:
        related_sources = select_related_sources(query, candidates)
        related_sources = expand_structured_context(related_sources, chunks)
        if usable_evidence(related_sources):
            return ChatResponse(
                answer=answer_related_context(query, related_sources),
                sources=related_sources,
                grounded=False,
                related=True,
            )
    except (RuntimeError, OpenAIError):
        # Context is optional. A model/API failure must not turn a non-answer
        # into an unsourced technical conclusion.
        return None
    return None


@app.get("/", include_in_schema=False)
def homepage() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict:
    chunks = load_chunks(KNOWLEDGE_BASE)
    verified = sum(chunk.verification_status == "confirmed_by_web" for chunk in chunks)
    different = sum(chunk.verification_status == "web_text_differs" for chunk in chunks)
    return {
        "status": "ok",
        "indexed_chunks": len(chunks),
        "canonical_provisions": sum(chunk.kind == "provision" for chunk in chunks),
        "complete_evidence_records": sum(chunk.complete_evidence for chunk in chunks),
        "secondary_source": {
            "url": "https://files.stroyinf.ru/Data1/2/2013/index.htm",
            "local_copy_available": HTML_SOURCE.exists(),
            "paragraphs_confirmed": verified,
            "paragraphs_with_text_differences": different,
        },
    }


@app.post("/search", response_model=list[SearchHit])
def document_search(request: SearchRequest) -> list[SearchHit]:
    chunks = load_chunks(KNOWLEDGE_BASE)
    if not chunks:
        raise HTTPException(status_code=503, detail="Knowledge base is not built. Run the ingestion command first.")
    return search(request.query, chunks, request.limit)


@app.post("/chat", response_model=ChatResponse)
def chat(request: SearchRequest) -> ChatResponse:
    if not is_georgian_question(request.query):
        return ChatResponse(
            answer="გთხოვთ, კითხვა ქართულ ენაზე მომაწოდოთ.",
            sources=[], grounded=False,
        )
    orientation_answer = about_document_answer(request.query)
    if orientation_answer:
        return ChatResponse(answer=orientation_answer, sources=[], grounded=False)
    compound_clarification = overground_compound_clarification(request.query)
    if compound_clarification:
        return ChatResponse(answer=compound_clarification, sources=[], grounded=False)
    if needs_clarification(request.query):
        return ChatResponse(
            answer=("დააზუსტეთ კითხვა: საუბარია საბავშვო ბაღში გაზის მოწყობილობების "
                    "დამონტაჟებაზე, გაზსადენის შენობის კედელზე გატარებაზე, თუ სხვა მოთხოვნაზე?"),
            sources=[], grounded=False,
        )
    chunks = load_chunks(KNOWLEDGE_BASE)
    if not chunks:
        raise HTTPException(status_code=503, detail="Knowledge base is not built. Run the ingestion command first.")
    parking_context = parking_related_answer(request.query)
    if parking_context:
        source_labels = {"4.3", "4.17", "4.28", "6.4", "6.21", "6.24"}
        parking_sources = [
            SearchHit(score=1.0, chunk=chunk)
            for chunk in chunks
            if chunk.paragraph in source_labels or chunk.source_label == "Таблица 6"
        ]
        if usable_evidence(parking_sources):
            return ChatResponse(
                answer=parking_context, sources=parking_sources, grounded=False, related=True,
            )
    wet_room_context = wet_room_related_answer(request.query)
    if wet_room_context:
        wet_room_sources = provision_source("6.37", chunks)
        if usable_evidence(wet_room_sources):
            return ChatResponse(
                answer=wet_room_context, sources=wet_room_sources, grounded=False, related=True,
            )
    checked_rule = checked_rule_answer(request.query)
    if checked_rule:
        answer, paragraph = checked_rule
        sources = provision_source(paragraph, chunks)
        if usable_evidence(sources):
            return ChatResponse(answer=answer, sources=sources, grounded=True)
    crossing_answer = overground_crossing_answer(request.query)
    if crossing_answer:
        sources = provision_source("4.57", chunks)
        if usable_evidence(sources):
            return ChatResponse(answer=crossing_answer, sources=sources, grounded=True)
    overview_answer = overground_overview_answer(request.query)
    if overview_answer:
        sources = broad_topic_sources(request.query, chunks)
        if usable_evidence(sources):
            return ChatResponse(answer=overview_answer, sources=sources, grounded=True)
    if not EMBEDDINGS.exists():
        raise HTTPException(status_code=503, detail="Multilingual search is not ready. Configure OPENAI_API_KEY and build embeddings.")
    try:
        sources = broad_topic_sources(request.query, chunks)
        if not sources:
            candidates = semantic_search(request.query, chunks, EMBEDDINGS, 12)
            sources = select_relevant_sources(request.query, candidates)
        sources = expand_structured_context(sources, chunks)
    except (RuntimeError, OpenAIError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    # Cross-language embeddings often have lower cosine scores than same-language matches.
    # Keep a conservative floor, then let the grounded-answer prompt reject insufficient evidence.
    if not sources:
        related = related_context_response(request.query, candidates, chunks)
        if related:
            return related
        return ChatResponse(
            answer="ამ კითხვაზე პასუხი მოცემულ СНиП 2.04.08-87 დოკუმენტში საკმარისი სანდოობით ვერ მოიძებნა.",
            sources=[], grounded=False,
        )
    if sources[0].score < 0.10:
        related = related_context_response(request.query, candidates, chunks)
        if related:
            return related
        return ChatResponse(
            answer="ამ კითხვაზე პასუხი მოცემულ СНиП 2.04.08-87 დოკუმენტში საკმარისი სანდოობით ვერ მოიძებნა.",
            sources=[], grounded=False,
        )
    if not usable_evidence(sources):
        related = related_context_response(request.query, candidates, chunks)
        if related:
            return related
        return ChatResponse(
            answer="ამ კითხვაზე სრულყოფილი, ზუსტად ციტირებადი ნორმატიული მტკიცებულება ვერ მოიძებნა.",
            sources=[], grounded=False,
        )
    try:
        answer = answer_question(request.query, sources)
    except ClarificationRequired as clarification:
        return ChatResponse(answer=clarification.message, sources=[], grounded=False)
    except (RuntimeError, OpenAIError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return ChatResponse(answer=answer, sources=sources, grounded=True)


app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")
