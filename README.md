# СНиП Chatbot

Initial backend for a source-grounded chatbot over СНиП documents. The Word file is the primary source because it best preserves tables and layout. The published HTML version is retained as a secondary verification source and fallback for text extraction.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m scripts.ingest_sources path\to\СНиП-2.04.08-87.docx
Copy-Item .env.example .env
# Set OPENAI_API_KEY in .env, then build multilingual embeddings once:
python -m scripts.build_embeddings
uvicorn app.main:app --reload
```

To retain a local, frozen copy of the supplementary web transcription, run:

```powershell
python -m scripts.download_web_source
```

The web copy is never used to silently replace a Word passage: its chunks are marked `source_type: html` and retain the original URL. During the combined build, it contributes only paragraph numbers absent from Word.

## Multilingual questions

The chatbot uses `text-embedding-3-small` to retrieve Russian evidence from Georgian or Russian questions, then generates a grounded answer in the user's language. The default 400-token answer cap keeps usage predictable. Set `OPENAI_API_KEY` only in `.env` locally or Railway Variables in production; never commit it.

Open `http://127.0.0.1:8000` to use the chatbot. `GET /health` reports whether the document has been indexed; `POST /search` exposes the retrieval layer for testing.

## Deployment

The included `Dockerfile`, `docker-compose.yml`, and `railway.json` deploy the same document-grounded application locally and on Railway. Commit the Word source with the project, push to GitHub, then create a Railway project from that repository.

With Docker Compose, the `data` folder is persisted on the host. On its first start with `OPENAI_API_KEY` configured, the container creates the knowledge base and multilingual embeddings automatically.
