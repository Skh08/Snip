from unittest import TestCase
from unittest.mock import patch

from app.language import (
    ABOUT_DOCUMENT_ANSWER,
    about_document_answer,
    checked_rule_answer,
    is_georgian_question,
    needs_clarification,
    overground_compound_clarification,
    overground_crossing_answer,
    overground_overview_answer,
)
from app.semantic import ClarificationRequired, _client, _normalize_answer_artifacts, _valid_final_answer


class LanguagePolicyTests(TestCase):
    def test_accepts_georgian_question(self) -> None:
        self.assertTrue(is_georgian_question("რა მოთხოვნებია მიწისზედა გაზსადენისთვის?"))

    def test_rejects_non_georgian_question(self) -> None:
        self.assertFalse(is_georgian_question("What are the requirements?"))
        self.assertFalse(is_georgian_question("Какие требования?"))

    def test_answers_document_orientation_without_rag(self) -> None:
        self.assertEqual(about_document_answer("რა დოკუმენტია ეს?"), ABOUT_DOCUMENT_ANSWER)
        self.assertEqual(about_document_answer("რას ეხება კითხვა-პასუხი?"), ABOUT_DOCUMENT_ANSWER)
        self.assertIsNone(about_document_answer("რას ეხება პ. 4.92?"))

    def test_overground_overview_is_a_checked_direct_answer(self) -> None:
        answer = overground_overview_answer("რა მოთხოვნებია მიწისზედა გაზსადენებისთვის?")
        self.assertIsNotNone(answer)
        self.assertIn("არაწვადი", answer)
        self.assertIsNone(overground_overview_answer("რა სიმაღლეზეა მიწისზედა გაზსადენი?"))

    def test_compound_overground_question_requests_the_missing_crossing_scope(self) -> None:
        answer = overground_compound_clarification("საყრდენებზე, გზის გადაკვეთაზე და კედელზე გატარებაზე")
        self.assertIsNotNone(answer)
        self.assertIn("დააზუსტეთ", answer)
        self.assertIsNone(
            overground_compound_clarification(
                "საყრდენებზე, ავტოგზის გადაკვეთაზე და კედელზე გატარებაზე"
            )
        )

    def test_overground_crossing_uses_height_rule_not_underground_depth(self) -> None:
        answer = overground_crossing_answer("მიწისზედა გაზსადენის ტრამვაის ლიანდაგზე გადაკვეთა")
        self.assertIsNotNone(answer)
        self.assertIn("სიმაღლე", answer)
        self.assertIsNone(overground_crossing_answer("მიწისქვეშა გაზსადენის ტრამვაის ლიანდაგზე გადაკვეთა"))

    def test_checked_rules_preserve_permissions_prohibitions_and_measurements(self) -> None:
        low_support = checked_rule_answer("თავისუფალ ტერიტორიაზე დაბალ საყრდენზე რა სიმაღლეზე შეიძლება მიწისზედა გაზსადენი?")
        self.assertEqual(low_support[1], "4.28")
        self.assertIn("დასაშვებია", low_support[0])
        self.assertIn("მილის ქვედა ნიშნულამდე", low_support[0])

        kindergarten = checked_rule_answer("შეიძლება საბავშვო დაწესებულების კედელზე ტრანზიტული გაზსადენის გატარება?")
        self.assertEqual(kindergarten[1], "4.22")
        self.assertIn("დაუშვებელია", kindergarten[0])

        corrosion = checked_rule_answer("როგორ უნდა დაიცვას მიწისზედა გაზსადენი ატმოსფერული კოროზიისგან?")
        self.assertEqual(corrosion[1], "4.81")
        self.assertIn("გრუნტის ორი ფენისა", corrosion[0])

    def test_final_answer_must_not_contain_foreign_or_banned_words(self) -> None:
        self.assertTrue(_valid_final_answer("გაზსადენის ჩაღრმავების სიღრმე უნდა იყოს არანაკლებ 1,0 მ."))
        self.assertTrue(_valid_final_answer("ტემპერატურა არის −40 °C-ზე დაბალი."))
        self.assertFalse(_valid_final_answer("გაზსადენი უნდა იყოს not less than 1.0 m."))
        self.assertFalse(_valid_final_answer("სიღრმე უნდა იყოს მთელყოფილად 1,0 მ."))
        self.assertFalse(_valid_final_answer("ტემპერატურა მეთოდი −45 °C-მდეა."))
        self.assertFalse(_valid_final_answer("ციტირებული მტკიცებულების მიხედვით, მოთხოვნა დაუშვებელია."))

    def test_ambiguous_kindergarten_question_requires_clarification(self) -> None:
        self.assertTrue(needs_clarification("საბავშვო ბაღებში გაზი შეიძლება?"))
        self.assertFalse(needs_clarification("საბავშვო ბაღში ტრანზიტული გაზსადენის გატარება შეიძლება?"))

    def test_normalizes_only_known_non_georgian_artifacts(self) -> None:
        self.assertEqual(
            _normalize_answer_artifacts("ციტირებული მტკიცებულების მიხედვით, პ. 4.22: 0,6 MPa."),
            "პ. 4.22: 0,6 მპა.",
        )

    def test_scope_request_is_valid_georgian_output(self) -> None:
        fallback = (
            "მიწისზედა გაზსადენებისთვის მოთხოვნები განთავსების პირობების მიხედვით განსხვავდება. "
            "დააზუსტეთ, საუბარია საყრდენებზე განთავსებაზე, გზის გადაკვეთაზე, შენობის კედელზე გატარებაზე თუ სხვა კონკრეტულ პირობაზე."
        )
        self.assertTrue(_valid_final_answer(fallback))
        self.assertEqual(ClarificationRequired(fallback).message, fallback)

    @patch("app.semantic.OpenAI")
    @patch.dict("os.environ", {"OPENAI_API_KEY": "  test-key\n"}, clear=False)
    def test_client_strips_surrounding_secret_whitespace(self, openai_mock) -> None:
        _client()
        openai_mock.assert_called_once_with(api_key="test-key")
