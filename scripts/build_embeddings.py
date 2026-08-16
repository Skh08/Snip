from pathlib import Path

from app.search import load_chunks
from app.semantic import EMBEDDING_MODEL, build_embeddings, embeddings_match_current_model

knowledge_base = Path("data/canonical_knowledge_base.json")
destination = Path("data/canonical_embeddings.json")
if embeddings_match_current_model(destination):
    print(f"Multilingual embeddings already use {EMBEDDING_MODEL}; no rebuild needed")
else:
    count = build_embeddings(load_chunks(knowledge_base), destination)
    print(f"Created {count} multilingual embeddings with {EMBEDDING_MODEL}")
