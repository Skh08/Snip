from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from openai import OpenAIError
from fastapi.staticfiles import StaticFiles

from .models import ChatResponse, SearchRequest, SearchHit
from .language import about_document_answer, is_georgian_question, needs_clarification
from .search import load_chunks, search
from .semantic import ClarificationRequired, answer_question, select_relevant_sources, semantic_search

BASE_DIR = Path(__file__).resolve().parents[1]
KNOWLEDGE_BASE = BASE_DIR / "data" / "knowledge_base.json"
EMBEDDINGS = BASE_DIR / "data" / "embeddings.json"
HTML_SOURCE = BASE_DIR / "data" / "snip_2.04.08-87.html"
app = FastAPI(title="СНиП Chatbot API", version="0.1.0")
STATIC_DIR = BASE_DIR / "static"


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
    if needs_clarification(request.query):
        return ChatResponse(
            answer=("დააზუსტეთ კითხვა: საუბარია საბავშვო ბაღში გაზის მოწყობილობების "
                    "დამონტაჟებაზე, გაზსადენის შენობის კედელზე გატარებაზე, თუ სხვა მოთხოვნაზე?"),
            sources=[], grounded=False,
        )
    chunks = load_chunks(KNOWLEDGE_BASE)
    if not chunks:
        raise HTTPException(status_code=503, detail="Knowledge base is not built. Run the ingestion command first.")
    if not EMBEDDINGS.exists():
        raise HTTPException(status_code=503, detail="Multilingual search is not ready. Configure OPENAI_API_KEY and build embeddings.")
    try:
        candidates = semantic_search(request.query, chunks, EMBEDDINGS, 8)
        sources = select_relevant_sources(request.query, candidates)
    except (RuntimeError, OpenAIError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    # Cross-language embeddings often have lower cosine scores than same-language matches.
    # Keep a conservative floor, then let the grounded-answer prompt reject insufficient evidence.
    if not sources or sources[0].score < 0.10:
        return ChatResponse(
            answer="ამ კითხვაზე პასუხი მოცემულ СНиП 2.04.08-87 დოკუმენტში საკმარისი სანდოობით ვერ მოიძებნა.",
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
