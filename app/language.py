"""Language guard for a Georgian-language public chatbot."""
from __future__ import annotations

import re

GEORGIAN_LETTER = re.compile(r"[\u10D0-\u10FF]")
KINDERGARTEN_RE = re.compile(r"საბავშვო\s*ბაღ|ბავშვთა\s*ბაღ", re.IGNORECASE)
ROUTING_CONTEXT_RE = re.compile(r"გაზსადენ|მილ|კედელ|ტრანზიტ|მოწყობილ|ქურა|წნევ|გატარ", re.IGNORECASE)
ABOUT_DOCUMENT_RE = re.compile(
    r"(?:რა\s+დოკუმენტია\s*(?:ეს)?|ეს\s+რა\s+დოკუმენტია|"
    r"(?:რას\s+ეხება|რის\s+შესახებაა)\s*(?:ეს|კითხვა(?:[-\s]*პასუხი)?|ჩატბოტი|დოკუმენტი)?)\s*[?!.]*$",
    re.IGNORECASE,
)

ABOUT_DOCUMENT_ANSWER = (
    "ეს არის СНиП 2.04.08-87 — გაზმომარაგების ნორმატიული დოკუმენტი. "
    "ჩატბოტი პასუხობს ამ დოკუმენტში მოცემულ მოთხოვნებზე: გაზსადენების დაგებაზე, "
    "გაზის წნევაზე, უსაფრთხოებაზე და გაზმომარაგების მოწყობილობებზე. "
    "კითხვა მოგვაწოდეთ ქართულად."
)

OVERGROUND_OVERVIEW_ANSWER = (
    "მიწისზედა გაზსადენები უნდა განთავსდეს ცალკე მდგომ არაწვადი მასალის საყრდენებზე, "
    "ესტაკადებსა და კოლონებზე, ან შენობების კედლებზე. ცალკე საყრდენებზე, კოლონებზე, "
    "ესტაკადებსა და სართულოვან კონსტრუქციებზე დასაშვებია ყველა წნევის გაზსადენი; "
    "შენობების კედლებზე გატარება კი დამოკიდებულია შენობის დანიშნულებასა და გაზის წნევაზე. "
    "საბავშვო დაწესებულებების, საავადმყოფოების, სკოლებისა და სანახაობრივი შენობების კედლებზე "
    "ტრანზიტული გატარება ყველა წნევის გაზსადენისთვის დაუშვებელია."
)

OVERGROUND_COMPOUND_CLARIFICATION = (
    "ეს სამი დამოუკიდებელი ნორმატიული შემთხვევაა. საყრდენებზე განთავსებისა და შენობის კედლებზე "
    "გატარების ძირითადი მოთხოვნები მოცემულია პ. 4.22-ში. გზის გადაკვეთაზე ზუსტი პასუხისთვის "
    "დააზუსტეთ, საუბარია ავტოგზაზე, რკინიგზაზე, ტრამვაის ლიანდაგზე თუ საფეხმავლო გზაზე."
)

OVERGROUND_CROSSING_ANSWER = (
    "რკინიგზის, ტრამვაის ლიანდაგის, ავტოგზის ან ტროლეიბუსის საკონტაქტო ქსელის გადაკვეთის ადგილას "
    "მიწისზედა გაზსადენის განთავსების სიმაღლე უნდა განისაზღვროს სნიპ II-89-80-ის მოთხოვნებით. "
    "ეს სნიპ 2.04.08-87 სიმაღლის ციფრულ მნიშვნელობას არ ადგენს."
)


def is_georgian_question(value: str) -> bool:
    """Accept questions containing Georgian script; numbers and punctuation are allowed."""
    return bool(GEORGIAN_LETTER.search(value))


def about_document_answer(value: str) -> str | None:
    """Answer public app-orientation questions without running RAG or the API."""
    return ABOUT_DOCUMENT_ANSWER if ABOUT_DOCUMENT_RE.search(value) else None


def needs_clarification(value: str) -> bool:
    """Avoid presenting one narrow rule as a general kindergarten gas decision."""
    return bool(
        KINDERGARTEN_RE.search(value)
        and "შეიძლება" in value
        and not ROUTING_CONTEXT_RE.search(value)
    )


def overground_overview_answer(value: str) -> str | None:
    """Return the fully checked overview for the standard's p. 4.22 topic."""
    normalized = value.casefold()
    if not ("მიწისზედა" in normalized and "გაზსადენ" in normalized and "მოთხოვნ" in normalized):
        return None
    qualifiers = ("სიმაღლ", "საყრდენ", "თავისუფალ", "კედელ", "გზ", "გადაკვეთ", "წნევ", "საბავშვ", "ტრანზიტ")
    return None if any(marker in normalized for marker in qualifiers) else OVERGROUND_OVERVIEW_ANSWER


def overground_compound_clarification(value: str) -> str | None:
    """Do not merge supports, walls, and road crossings into one guessed rule."""
    normalized = value.casefold()
    crossing_kind_given = any(marker in normalized for marker in (
        "ავტოგზ", "რკინიგზ", "ტრამვ", "საფეხმავლ",
    ))
    if not crossing_kind_given and all(marker in normalized for marker in ("საყრდენ", "კედელ", "გზ")):
        return OVERGROUND_COMPOUND_CLARIFICATION
    return None


def overground_crossing_answer(value: str) -> str | None:
    """Prevent underground crossing depths from answering an overground query."""
    normalized = value.casefold()
    crossing_markers = ("ავტოგზ", "რკინიგზ", "ტრამვ", "ტროლეიბ")
    if "მიწისზედა" in normalized and "გაზსადენ" in normalized and any(marker in normalized for marker in crossing_markers):
        return OVERGROUND_CROSSING_ANSWER
    return None
