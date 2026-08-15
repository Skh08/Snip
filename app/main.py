from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import ChatResponse, SearchRequest, SearchHit
from .search import load_chunks, search
from .semantic import answer_question, semantic_search

BASE_DIR = Path(__file__).resolve().parents[1]
KNOWLEDGE_BASE = BASE_DIR / "data" / "knowledge_base.json"
EMBEDDINGS = BASE_DIR / "data" / "embeddings.json"
app = FastAPI(title="СНиП Chatbot API", version="0.1.0")
STATIC_DIR = BASE_DIR / "static"


@app.get("/", include_in_schema=False)
def homepage() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "indexed_chunks": len(load_chunks(KNOWLEDGE_BASE))}


@app.post("/search", response_model=list[SearchHit])
def document_search(request: SearchRequest) -> list[SearchHit]:
    chunks = load_chunks(KNOWLEDGE_BASE)
    if not chunks:
        raise HTTPException(status_code=503, detail="Knowledge base is not built. Run the ingestion command first.")
    return search(request.query, chunks, request.limit)


@app.post("/chat", response_model=ChatResponse)
def chat(request: SearchRequest) -> ChatResponse:
    chunks = load_chunks(KNOWLEDGE_BASE)
    if not chunks:
        raise HTTPException(status_code=503, detail="Knowledge base is not built. Run the ingestion command first.")
    if not EMBEDDINGS.exists():
        raise HTTPException(status_code=503, detail="Multilingual search is not ready. Configure OPENAI_API_KEY and build embeddings.")
    try:
        sources = semantic_search(request.query, chunks, EMBEDDINGS, min(request.limit, 4))
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    if not sources or sources[0].score < 0.25:
        return ChatResponse(
            answer="ამ კითხვაზე პასუხი მოცემულ СНиП 2.04.08-87 დოკუმენტში საკმარისი სანდოობით ვერ მოიძებნა.",
            sources=[], grounded=False,
        )
    answer = answer_question(request.query, sources)
    return ChatResponse(answer=answer, sources=sources, grounded=True)


app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")
