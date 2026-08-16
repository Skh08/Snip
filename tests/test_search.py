from unittest import TestCase

from app.models import Chunk, SearchHit
from app.search import fuse_search_hits, keyword_search


def _chunk(identifier: str, ordinal: int, text: str, paragraph: str | None = None) -> Chunk:
    return Chunk(
        id=identifier,
        ordinal=ordinal,
        text=text,
        paragraph=paragraph,
        source_label=f"п. {paragraph}" if paragraph else f"абзац {ordinal}",
        section="4. Наружные газопроводы",
    )


class HybridSearchTests(TestCase):
    def test_keyword_search_prioritizes_exact_provision_number(self) -> None:
        other = _chunk("other", 1, "Глубину прокладки следует принимать по проекту.", "4.17")
        target = _chunk("target", 2, "Глубину прокладки до верха трубы следует предусматривать не менее 1,0 м.", "4.92")
        hits = keyword_search("требования п. 4.92", [other, target], 2)
        self.assertEqual(hits[0].chunk.id, "target")

    def test_exact_lexical_match_can_correct_semantic_near_match(self) -> None:
        near = _chunk("near", 1, "Глубину прокладки следует принимать по проекту.", "4.17")
        target = _chunk("target", 2, "Глубину прокладки до верха трубы следует предусматривать не менее 1,0 м.", "4.92")
        semantic = [SearchHit(score=0.95, chunk=near), SearchHit(score=0.70, chunk=target)]
        lexical = [SearchHit(score=12.0, chunk=target)]
        hits = fuse_search_hits(semantic, lexical, 2)
        self.assertEqual(hits[0].chunk.id, "target")
