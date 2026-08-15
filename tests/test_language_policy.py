from unittest import TestCase
from unittest.mock import patch

from app.language import is_georgian_question, needs_clarification
from app.semantic import _client, _valid_final_answer


class LanguagePolicyTests(TestCase):
    def test_accepts_georgian_question(self) -> None:
        self.assertTrue(is_georgian_question("რა მოთხოვნებია მიწისზედა გაზსადენისთვის?"))

    def test_rejects_non_georgian_question(self) -> None:
        self.assertFalse(is_georgian_question("What are the requirements?"))
        self.assertFalse(is_georgian_question("Какие требования?"))

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

    @patch("app.semantic.OpenAI")
    @patch.dict("os.environ", {"OPENAI_API_KEY": "  test-key\n"}, clear=False)
    def test_client_strips_surrounding_secret_whitespace(self, openai_mock) -> None:
        _client()
        openai_mock.assert_called_once_with(api_key="test-key")
