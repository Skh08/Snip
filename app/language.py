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

KITCHEN_GAS_STOVE_ANSWER = (
    "საცხოვრებელ სახლში გაზქურა უნდა დამონტაჟდეს სამზარეულოში, რომლის სიმაღლე არანაკლებ 2,2 მ-ია "
    "და რომელსაც აქვს გასაღები სარკმელი ან ფრამუგა, გამწოვი სავენტილაციო არხი და ბუნებრივი განათება. "
    "პ. 6.29 ფართობს კვადრატულ მეტრებში არ ადგენს: სამზარეულოს მინიმალური მოცულობა 2-სანთურიანი "
    "გაზქურისთვის 8 მ³, 3-სანთურიანისთვის 12 მ³, ხოლო 4-სანთურიანისთვის 15 მ³-ია; ფართობის დასადგენად "
    "საჭიროა ოთახის ფაქტობრივი სიმაღლის გათვალისწინება."
)

WET_ROOM_RELATED_ANSWER = (
    "სნიპ 2.04.08-87-ში სველ წერტილში ან აბაზანაში გაზსადენის ტრანზიტული გატარების ცალკე წესი პირდაპირ "
    "არ არის მოცემული. ცნობისთვის, პ. 6.37 აბაზანაში გაზის წყლის გამაცხელებლის, გათბობის ქვაბისა და "
    "გათბობის მოწყობილობების მონტაჟს დაუშვებლად მიიჩნევს; ეს მოთხოვნა თავად გაზსადენის გატარების "
    "ნებართვას ან აკრძალვას არ ადგენს."
)

PARKING_RELATED_ANSWER = (
    "სნიპ 2.04.08-87 არ შეიცავს ავტოსადგომში ან პარკინგში გაზსადენის გაყვანის ერთიან, "
    "სპეციალურ ნორმას; ამიტომ მხოლოდ ამ დოკუმენტით ზოგადი „შეიძლება/არ შეიძლება“ დასკვნა ვერ კეთდება. "
    "ცნობისთვის, კონკრეტული ტრასის შეფასებისას დაკავშირებულია შემდეგი მოთხოვნები: დასახლების ტერიტორიაზე "
    "გარე გაზსადენი, როგორც წესი, მიწისქვეშ უნდა დაიგოს; მიწისქვეშა გაზსადენის ჩაღრმავება მილის ან "
    "დამცავი გარსაცმის ზედა ნიშნულამდე არანაკლებ 0,8 მ-ია, ხოლო 0,6 მ დასაშვებია მხოლოდ იქ, სადაც "
    "ტრანსპორტის მოძრაობა არ არის გათვალისწინებული. თავისუფალ ტერიტორიაზე, ტრანსპორტისა და ადამიანების "
    "გადაადგილების გარეთ, დაბალ საყრდენებზე დაგება დასაშვებია მიწიდან მილის ქვედა ზედაპირამდე სულ მცირე "
    "0,35 მ სიმაღლით. საყრდენებზე განთავსებული მიწისზედა ან ზედაპირული (მიწაყრილის გარეშე) გაზსადენისთვის "
    "გზამდე მინიმალური მანძილი 1,5 მ-ია. თუ საუბარია შენობის შიგნით არსებულ ტრასაზე, გაზსადენი, როგორც წესი, "
    "ღიად უნდა დაიგოს; ადამიანების გასასვლელში მილის ქვედა ზედაპირი იატაკიდან არანაკლებ 2,2 მ სიმაღლეზეა, "
    "ხოლო სამშენებლო კონსტრუქციების გადაკვეთისას ვერტიკალური გაზსადენი დამცავ გარსაცმში უნდა მოთავსდეს. "
    "ეს პუნქტები საინფორმაციოდ არის მოყვანილი და არ წარმოადგენს ავტოსადგომისთვის სპეციალურ ნებართვას ან აკრძალვას."
)


def checked_rule_answer(value: str) -> tuple[str, str] | None:
    """Return a fixed Georgian rendering for high-risk, unambiguous rules.

    These provisions contain measurements, permissions, or prohibitions where
    a creative translation would be unacceptable.  The tuple is answer text
    and the exact provision number used to display the source in the UI.
    """
    normalized = value.casefold()
    refers_to_kitchen_gas_stove = (
        any(marker in normalized for marker in ("სამზარეულ", "გაზქურა", "გაზის ქურა"))
        and any(marker in normalized for marker in (
            "სიმაღლ", "ჭერ", "კვადრატ", "ფართობ", "მოცულ", "სანთურ", "მოწყობ",
        ))
    )
    if refers_to_kitchen_gas_stove:
        return KITCHEN_GAS_STOVE_ANSWER, "6.29"
    asks_pipe_material = any(marker in normalized for marker in (
        "როგორი მილ", "რომელი მილ", "რა მილი", "მილის მასალ", "ფოლადის მილ",
    ))
    refers_to_inside_building = any(marker in normalized for marker in (
        "სახლ", "შენობის შიგნით", "შიდა გაზსადენ", "შენობაში",
    ))
    if asks_pipe_material and refers_to_inside_building:
        return (
            "შენობის შიგნით გასატარებელი გაზსადენი უნდა მოეწყოს ფოლადის მილებით, რომლებიც აკმაყოფილებს "
            "11-ე განყოფილების მოთხოვნებს. მოძრავი აგრეგატების, გადასატანი სანთურების, გაზის ხელსაწყოების, "
            "საკონტროლო-საზომი და ავტომატიკის მოწყობილობების შესაერთებლად დასაშვებია რეზინისა და "
            "რეზინ-ქსოვილოვანი შლანგები, მათი მოცემული აირის წნევისა და ტემპერატურისადმი მდგრადობის გათვალისწინებით.",
            "6.2",
        )
    if "პოლიეთილენ" in normalized and "ჩაღრმავ" in normalized:
        return (
            "პოლიეთილენის გაზსადენის ჩაღრმავების სიღრმე მილის ზედა ნიშნულამდე უნდა იყოს "
            "არანაკლებ 1,0 მ. იმ რაიონებში, სადაც გარე ჰაერის საანგარიშო ტემპერატურა −40 °C-ზე "
            "დაბალია, −45 °C-მდე ჩათვლით, სიღრმე უნდა იყოს არანაკლებ 1,4 მ.",
            "4.92",
        )
    if "თავისუფალ" in normalized and "დაბალ საყრდენ" in normalized and "მიწისზედა" in normalized:
        return (
            "თავისუფალ ტერიტორიაზე, სადაც სატრანსპორტო მოძრაობა და ადამიანების გადაადგილება არ ხდება, "
            "მიწისზედა გაზსადენის დაბალ საყრდენებზე დაგება დასაშვებია, თუ მიწიდან მილის ქვედა ნიშნულამდე "
            "სიმაღლე არანაკლებ 0,35 მ-ია.",
            "4.28",
        )
    if "საბავშვ" in normalized and "კედელ" in normalized and "ტრანზიტ" in normalized:
        return (
            "საბავშვო დაწესებულებების შენობების კედლებზე ყველა წნევის გაზსადენის ტრანზიტული გატარება დაუშვებელია.",
            "4.22",
        )
    if "ატმოსფერულ" in normalized and "კოროზ" in normalized and "მიწისზედა" in normalized:
        return (
            "მიწისზედა გაზსადენი ატმოსფერული კოროზიისგან უნდა დაიცვას საფარმა, რომელიც შედგება გრუნტის "
            "ორი ფენისა და გარე სამუშაოებისთვის განკუთვნილი საღებავის, ლაქის ან ემალის ორი ფენისგან. "
            "საფარი უნდა შეესაბამებოდეს მშენებლობის რაიონში გარე ჰაერის საანგარიშო ტემპერატურას.",
            "4.81",
        )
    if "ჩაღრმავ" in normalized and "გაზსადენ" in normalized and "პოლიეთილენ" not in normalized:
        return (
            "გაზსადენის ჩაღრმავების სიღრმე მილის ან დამცავი გარსაცმის ზედა ნიშნულამდე უნდა იყოს არანაკლებ 0,8 მ. "
            "იმ ადგილებში, სადაც ტრანსპორტის მოძრაობა არ არის გათვალისწინებული, დასაშვებია სიღრმის 0,6 მ-მდე შემცირება.",
            "4.17",
        )
    return None


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


def parking_related_answer(value: str) -> str | None:
    """Give verified related rules without inventing a parking-specific decision."""
    normalized = value.casefold()
    parking_terms = ("ავტოსადგომ", "პარკინგ", "ავტოფარეხ")
    pipeline_terms = ("გაზსადენ", "გაზის მილ", "გაზის მილი")
    if any(term in normalized for term in parking_terms) and any(term in normalized for term in pipeline_terms):
        return PARKING_RELATED_ANSWER
    return None


def wet_room_related_answer(value: str) -> str | None:
    """Surface the verified bathroom-appliance restriction without extending it to pipes."""
    normalized = value.casefold()
    wet_room_terms = ("სველ წერტილ", "აბაზან", "საპირფარეშ", "საშხაპ")
    pipeline_terms = ("გაზსადენ", "გაზის მილ", "გაზის მილი")
    if any(term in normalized for term in wet_room_terms) and any(term in normalized for term in pipeline_terms):
        return WET_ROOM_RELATED_ANSWER
    return None
