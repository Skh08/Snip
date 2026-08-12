import argparse
from pathlib import Path

from app.knowledge_base import build

parser = argparse.ArgumentParser(description="Build the source-grounded СНиП knowledge base.")
parser.add_argument("docx", type=Path, help="Authoritative Word source")
parser.add_argument("--html", type=Path, default=Path("data/snip_2.04.08-87.html"))
parser.add_argument("--output", type=Path, default=Path("data/knowledge_base.json"))
args = parser.parse_args()
count = build(args.docx, args.output, args.html)
print(f"Indexed {count} source chunks in {args.output}")
