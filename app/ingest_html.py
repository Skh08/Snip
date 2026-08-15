"""Secondary ingestion of the published HTML transcription of СНиП 2.04.08-87*."""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

from .ingest import APPENDIX_RE, PARAGRAPH_RE, SECTION_RE, _clean, _label
from .models import Chunk

SOURCE_URL = "https://files.stroyinf.ru/Data1/2/2013/index.htm"


def download_html(destination: Path, url: str = SOURCE_URL) -> None:
    request = Request(url, headers={"User-Agent": "SNIP-Source-Verification/1.0"})
    with urlopen(request, timeout=30) as response:  # nosec B310 - fixed public source URL
        content = response.read()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)


class _TextBlocks(HTMLParser):
    block_tags = {"h1", "h2", "h3", "p", "li"}

    def __init__(self) -> None:
        super().__init__()
        self._depth = 0
        self._parts: list[str] = []
        self.blocks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self.block_tags:
            self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.block_tags and self._depth:
            self._depth -= 1
            if not self._depth and self._parts:
                self.blocks.append(_clean(" ".join(self._parts)))
                self._parts = []

    def handle_data(self, data: str) -> None:
        if self._depth:
            self._parts.append(data)


def parse_html(path: Path, source_url: str = SOURCE_URL) -> list[Chunk]:
    parser = _TextBlocks()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    section: str | None = None
    chunks: list[Chunk] = []
    ordinal = 0
    # The publication uses a legacy table layout; get visible text blocks in reading order.
    for text in parser.blocks:
        if len(text) < 4 or text in {"На главную", "База 1", "База 2", "База 3"}:
            continue
        if SECTION_RE.match(text) or APPENDIX_RE.match(text):
            section = text
        match = PARAGRAPH_RE.match(text)
        paragraph = match.group(1) if match else None
        ordinal += 1
        chunks.append(Chunk(
            id=f"web-{ordinal}", text=text, section=section, paragraph=paragraph,
            source_label=_label(section, paragraph, f"web block {ordinal}"), ordinal=ordinal,
            source_type="html", source_url=source_url,
        ))
    return chunks
