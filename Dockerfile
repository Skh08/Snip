FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["sh", "-c", "set -e; if [ ! -f data/snip_2.04.08-87.html ]; then python -m scripts.download_web_source || echo 'Secondary web verification source unavailable; continuing with the Word source.'; fi; test -f data/canonical_knowledge_base.json || python -m scripts.ingest_sources data/snip-20408-87.docx; if [ -n \"$OPENAI_API_KEY\" ]; then python -m scripts.build_embeddings; fi; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
