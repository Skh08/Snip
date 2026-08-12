import argparse
from pathlib import Path

from app.ingest import write_knowledge_base


parser = argparse.ArgumentParser(description="Create a searchable СНиП knowledge base from a DOCX file.")
parser.add_argument("source", type=Path)
parser.add_argument("--output", type=Path, default=Path("data/knowledge_base.json"))
args = parser.parse_args()
count = write_knowledge_base(args.source, args.output)
print(f"Indexed {count} chunks in {args.output}")
