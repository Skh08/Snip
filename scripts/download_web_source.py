from pathlib import Path

from app.ingest_html import SOURCE_URL, download_html

destination = Path("data/snip_2.04.08-87.html")
download_html(destination)
print(f"Saved {SOURCE_URL} to {destination}")
