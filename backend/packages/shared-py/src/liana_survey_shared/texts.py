"""Fixed texts readers see, in each survey language (English, Finnish, Swedish).

The survey creator writes the questions and the thank-you message. Everything
else a reader sees (page headings, default messages, button labels) comes from
here, in the survey's language. Unknown languages fall back to English.
"""

from enum import StrEnum


class Language(StrEnum):
    en = "en"  # English
    fi = "fi"  # suomi
    sv = "sv"  # svenska


DEFAULT_LANGUAGE = Language.en

TEXTS: dict[str, dict[Language, str]] = {
    # Thank-you page
    "thanks_heading": {
        Language.en: "Thank you!",
        Language.fi: "Kiitos!",
        Language.sv: "Tack!",
    },
    "thanks_default": {
        Language.en: "Your answer was saved.",
        Language.fi: "Vastauksesi on tallennettu.",
        Language.sv: "Ditt svar har sparats.",
    },
    # Pages for answers that can't be taken
    "problem_heading": {
        Language.en: "We couldn’t take this answer",
        Language.fi: "Emme voineet ottaa vastaustasi vastaan",
        Language.sv: "Vi kunde inte ta emot ditt svar",
    },
    "closed": {
        Language.en: "This survey is closed and no longer takes answers.",
        Language.fi: "Tämä kysely on suljettu eikä ota enää vastauksia.",
        Language.sv: "Den här enkäten är stängd och tar inte längre emot svar.",
    },
    "full": {
        Language.en: "This survey has all the answers it needs. Thank you for wanting to answer.",
        Language.fi: (
            "Kyselyyn on saatu kaikki tarvittavat vastaukset. Kiitos, että halusit vastata."
        ),
        Language.sv: "Enkäten har fått alla svar den behöver. Tack för att du ville svara.",
    },
    "not_open": {
        Language.en: "This survey is not open yet.",
        Language.fi: "Tämä kysely ei ole vielä avoinna.",
        Language.sv: "Den här enkäten är inte öppen ännu.",
    },
    "wrong_survey": {
        Language.en: "This answer link does not fit this survey.",
        Language.fi: "Tämä vastauslinkki ei kuulu tähän kyselyyn.",
        Language.sv: "Den här svarslänken hör inte till den här enkäten.",
    },
    "no_answer": {
        Language.en: "Choose an answer in the email to answer this survey.",
        Language.fi: "Valitse vastaus sähköpostista vastataksesi kyselyyn.",
        Language.sv: "Välj ett svar i e-postmeddelandet för att svara på enkäten.",
    },
    "not_a_choice": {
        Language.en: "This answer is not one of the choices.",
        Language.fi: "Tämä vastaus ei ole yksi vaihtoehdoista.",
        Language.sv: "Det här svaret är inte ett av alternativen.",
    },
    "link_not_complete": {
        Language.en: "This link is not complete or not valid. Open it again from your email.",
        Language.fi: "Linkki on puutteellinen tai virheellinen. Avaa se uudelleen sähköpostista.",
        Language.sv: "Länken är ofullständig eller ogiltig. Öppna den igen från e-postmeddelandet.",
    },
    "try_again": {
        Language.en: (
            "We couldn’t save your answer right now. Please open the link again in a moment."
        ),
        Language.fi: (
            "Emme voineet tallentaa vastaustasi juuri nyt. Avaa linkki uudelleen hetken kuluttua."
        ),
        Language.sv: "Vi kunde inte spara ditt svar just nu. Öppna länken igen om en stund.",
    },
    # Newsletter snippet: thumbs buttons and the line under them
    "thumbs_down": {
        Language.en: "Not for me",
        Language.fi: "Ei minulle",
        Language.sv: "Inte för mig",
    },
    "thumbs_ok": {
        Language.en: "Good",
        Language.fi: "Hyvä",
        Language.sv: "Bra",
    },
    "thumbs_up": {
        Language.en: "Loved it",
        Language.fi: "Tykkäsin",
        Language.sv: "Älskade det",
    },
    "snippet_footer": {
        Language.en: "One tap. Anonymous unless you ask to be contacted.",
        Language.fi: "Yksi napautus. Nimetön, ellet pyydä yhteydenottoa.",
        Language.sv: "Ett tryck. Anonymt om du inte ber om att bli kontaktad.",
    },
}


def language_or_default(language: str | None) -> Language:
    """The language as a Language, or English when it is missing or unknown."""
    try:
        return Language(language)
    except ValueError:
        return DEFAULT_LANGUAGE


def text(key: str, language: str | None = None) -> str:
    """The fixed text `key` in `language`, or in English for unknown languages."""
    return TEXTS[key][language_or_default(language)]
