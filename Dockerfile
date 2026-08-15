FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["sh", "-c", "test -f data/knowledge_base.json || python -m scripts.ingest_sources data/snip-20408-87.docx; if [ -n \"$OPENAI_API_KEY\" ] && [ ! -f data/embeddings.json ]; then python -m scripts.build_embeddings; fi; exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
