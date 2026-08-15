from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.ingest import parse_docx
from app.knowledge_base import _verification_status


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
