from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.ingest import parse_docx
from app.canonical import canonicalize
from app.knowledge_base import _verification_status
from app.models import SearchHit
from app.validation import usable_evidence


def _document(*texts: str) -> SimpleNamespace:
    return SimpleNamespace(
        paragraphs=[SimpleNamespace(text=text) for text in texts],
        tables=[],
    )


class IngestionTests(TestCase):
    def test_web_comparison_ignores_layout_spacing(self) -> None:
        self.assertEqual(
            _verification_status("4.22 Газопроводы следует прокладывать", "4.22 Г а зопроводы следует прокладывать"),
            "confirmed_by_web",
        )

    def test_continuations_keep_their_regulatory_paragraph_number(self) -> None:
        document = _document(
            "4. НАРУЖНЫЕ ГАЗОПРОВОДЫ И СООРУЖЕНИЯ",
            "4.22. Надземные газопроводы следует прокладывать на опорах.",
            "При этом разрешается прокладка:",
            "по стенам зданий детских учреждений - газопроводов всех давлений;",
        )
        with patch("app.ingest.Document", return_value=document):
            chunks = parse_docx("unused.docx")

        self.assertEqual(chunks[1].source_label, "п. 4.22")
        self.assertEqual(chunks[2].source_label, "п. 4.22")
        self.assertEqual(chunks[3].source_label, "п. 4.22")

    def test_numbered_table_note_is_not_mistaken_for_a_chapter(self) -> None:
        document = _document(
            "3. РАСЧЕТНЫЕ РАСХОДЫ ГАЗА",
            "Таблица 2",
            "Строка таблицы",
            "2. При применении газа для лабораторных нужд следует учитывать норму.",
            "3.4. Годовые расходы газа следует определять расчетом.",
        )
        with patch("app.ingest.Document", return_value=document):
            chunks = parse_docx("unused.docx")

        self.assertEqual(chunks[2].source_label, "Таблица 2")
        self.assertEqual(chunks[3].section, "3. РАСЧЕТНЫЕ РАСХОДЫ ГАЗА")
        self.assertEqual(chunks[4].source_label, "п. 3.4")

    def test_title_case_chapter_is_recognized_but_a_note_is_not(self) -> None:
        document = _document(
            "4. Наружные газопроводы и сооружения",
            "4.1. Требования распространяются на наружные газопроводы.",
            "2. При применении газа следует учитывать норму.",
        )
        with patch("app.ingest.Document", return_value=document):
            chunks = parse_docx("unused.docx")

        self.assertEqual(chunks[1].section, "4. Наружные газопроводы и сооружения")
        self.assertEqual(chunks[2].section, "4. Наружные газопроводы и сооружения")

    def test_canonical_record_merges_provision_and_excludes_subsection_title(self) -> None:
        document = _document(
            "4. НАРУЖНЫЕ ГАЗОПРОВОДЫ И СООРУЖЕНИЯ",
            "4.21. Правило для подземных газопроводов.",
            "Надземные и наземные газопроводы",
            "4.22. Надземные газопроводы следует прокладывать на опорах.",
            "При этом разрешается прокладка на колоннах.",
        )
        with patch("app.ingest.Document", return_value=document):
            records = canonicalize(parse_docx("unused.docx"))

        provision = next(record for record in records if record.paragraph == "4.22")
        self.assertEqual(provision.kind, "provision")
        self.assertTrue(provision.complete_evidence)
        self.assertEqual(provision.fragment_count, 2)
        self.assertEqual(provision.subsection, "Надземные и наземные газопроводы")
        self.assertIn("на колоннах", provision.text)
        self.assertNotIn("Надземные и наземные газопроводы", next(record for record in records if record.paragraph == "4.21").text)

    def test_answer_evidence_must_be_a_complete_canonical_record(self) -> None:
        document = _document("4.22. Надземные газопроводы следует прокладывать на опорах.")
        with patch("app.ingest.Document", return_value=document):
            record = canonicalize(parse_docx("unused.docx"))[0]

        self.assertTrue(usable_evidence([SearchHit(score=1.0, chunk=record)]))
        self.assertFalse(usable_evidence([SearchHit(score=1.0, chunk=record.model_copy(update={"complete_evidence": False}))]))
