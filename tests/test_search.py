from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.models import Chunk, SearchHit
from app.search import broad_topic_sources, fuse_search_hits, keyword_search, provision_source
from app.semantic import select_relevant_sources


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

    def test_keyword_search_prefers_numbered_rule_over_heading(self) -> None:
        heading = _chunk("heading", 1, "Надземные и наземные газопроводы")
        rule = _chunk(
            "rule", 2,
            "4.22. Надземные газопроводы следует прокладывать на отдельно стоящих опорах.",
            "4.22",
        )
        unrelated = _chunk("unrelated", 3, "Дополнительные требования к системам газоснабжения")

        hits = keyword_search("требования надземных газопроводов", [heading, rule, unrelated], 3)

        self.assertEqual(hits[0].chunk.id, "rule")

    def test_broad_overground_question_uses_general_rule_not_exception(self) -> None:
        general = _chunk(
            "general", 1,
            "4.22. Надземные газопроводы следует прокладывать на отдельно стоящих опорах.",
            "4.22",
        )
        exception = _chunk("exception", 2, "10.4. Особые требования в вечномерзлых грунтах.", "10.4")

        hits = broad_topic_sources("რა მოთხოვნებია მიწისზედა გაზსადენებისთვის?", [general, exception])

        self.assertEqual([hit.chunk.id for hit in hits], ["general"])

    def test_qualified_overground_question_keeps_hybrid_search_available(self) -> None:
        general = _chunk("general", 1, "4.22. Надземные газопроводы.", "4.22")
        self.assertEqual(
            broad_topic_sources("რა სიმაღლეზე უნდა განთავსდეს მიწისზედა გაზსადენი?", [general]),
            [],
        )

    def test_source_selector_can_abstain_instead_of_using_first_weak_match(self) -> None:
        candidate = _chunk("candidate", 1, "4.22. Надземные газопроводы.", "4.22").model_copy(
            update={"kind": "provision", "complete_evidence": True}
        )
        client = SimpleNamespace(
            responses=SimpleNamespace(create=lambda **_: SimpleNamespace(output_text="[]"))
        )
        with patch("app.semantic._client", return_value=client):
            selected = select_relevant_sources("რა არის ბეტონის სიმტკიცე?", [SearchHit(score=1.0, chunk=candidate)])

        self.assertEqual(selected, [])

    def test_provision_source_requires_complete_canonical_record(self) -> None:
        complete = _chunk("complete", 1, "4.57. Высота прокладки.", "4.57").model_copy(
            update={"kind": "provision", "complete_evidence": True}
        )
        incomplete = _chunk("incomplete", 2, "4.57. Фрагмент.", "4.57")
        self.assertEqual([hit.chunk.id for hit in provision_source("4.57", [incomplete, complete])], ["complete"])
