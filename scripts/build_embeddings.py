from pathlib import Path

from app.search import load_chunks
from app.semantic import build_embeddings

knowledge_base = Path("data/knowledge_base.json")
count = build_embeddings(load_chunks(knowledge_base), Path("data/embeddings.json"))
print(f"Created {count} multilingual embeddings")
