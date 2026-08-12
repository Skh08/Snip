from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from .models import ChatResponse, SearchRequest, SearchHit
from .search import load_chunks, search

BASE_DIR = Path(__file__).resolve().parents[1]
KNOWLEDGE_BASE = BASE_DIR / "data" / "knowledge_base.json"
app = FastAPI(title="СНиП Chatbot API", version="0.1.0")
STATIC_DIR = BASE_DIR / "static"


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
    sources = search(request.query, chunks, min(request.limit, 4))
    if not sources or sources[0].score < 0.2:
        return ChatResponse(
            answer="ამ კითხვაზე პასუხი მოცემულ СНиП 2.04.08-87 დოკუმენტში საკმარისი სანდოობით ვერ მოიძებნა.",
            sources=[], grounded=False,
        )
    excerpts = "\n\n".join(f"{item.chunk.source_label}: {item.chunk.text}" for item in sources[:3])
    return ChatResponse(answer=excerpts, sources=sources, grounded=True)


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
