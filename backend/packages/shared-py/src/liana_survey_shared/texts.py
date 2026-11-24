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
    # Survey link page (#105): the whole survey, from a plain link or QR code
    "survey_heading": {
        Language.en: "Survey",
        Language.fi: "Kysely",
        Language.sv: "Enkät",
    },
    "submit": {
        Language.en: "Submit",
        Language.fi: "Lähetä",
        Language.sv: "Skicka",
    },
    "optional": {
        Language.en: "(optional)",
        Language.fi: "(valinnainen)",
        Language.sv: "(valfritt)",
    },
    "choose": {
        Language.en: "Choose…",
        Language.fi: "Valitse…",
        Language.sv: "Välj…",
    },
    "nps_low": {
        Language.en: "Not at all likely",
        Language.fi: "Ei lainkaan todennäköistä",
        Language.sv: "Inte alls sannolikt",
    },
    "nps_high": {
        Language.en: "Extremely likely",
        Language.fi: "Erittäin todennäköistä",
        Language.sv: "Mycket sannolikt",
    },
    "csat_1": {
        Language.en: "Very dissatisfied",
        Language.fi: "Erittäin tyytymätön",
        Language.sv: "Mycket missnöjd",
    },
    "csat_2": {
        Language.en: "Dissatisfied",
        Language.fi: "Tyytymätön",
        Language.sv: "Missnöjd",
    },
    "csat_3": {
        Language.en: "Neutral",
        Language.fi: "Neutraali",
        Language.sv: "Neutral",
    },
    "csat_4": {
        Language.en: "Satisfied",
        Language.fi: "Tyytyväinen",
        Language.sv: "Nöjd",
    },
    "csat_5": {
        Language.en: "Very satisfied",
        Language.fi: "Erittäin tyytyväinen",
        Language.sv: "Mycket nöjd",
    },
    # Reasons questions saved without a heading, per survey type
    "reasons_thumbs": {
        Language.en: "What went wrong?",
        Language.fi: "Mikä meni pieleen?",
        Language.sv: "Vad blev fel?",
    },
    "reasons_nps": {
        Language.en: "What is the main reason for your score?",
        Language.fi: "Mikä on tärkein syy arvosanaasi?",
        Language.sv: "Vad är främsta skälet till ditt betyg?",
    },
    "reasons_csat": {
        Language.en: "What could we improve?",
        Language.fi: "Mitä voisimme parantaa?",
        Language.sv: "Vad kan vi förbättra?",
    },
    "reasons_if_not_for_me": {
        Language.en: "Only if you chose “Not for me”.",
        Language.fi: "Vain jos valitsit ”Ei minulle”.",
        Language.sv: "Endast om du valde ”Inte för mig”.",
    },
    # Follow-up page after a one-tap answer from an email (Bug 3: saved by the page,
    # not by opening the link, so mail scanners do not answer). {answer} is the answer.
    "your_answer": {
        Language.en: "Your answer: {answer}",
        Language.fi: "Vastauksesi: {answer}",
        Language.sv: "Ditt svar: {answer}",
    },
    "tap_saving": {
        Language.en: "Saving your answer…",
        Language.fi: "Tallennetaan vastaustasi…",
        Language.sv: "Ditt svar sparas…",
    },
    "tap_saved": {
        Language.en: "Thanks, your answer is saved. Everything below is optional.",
        Language.fi: "Kiitos, vastauksesi on tallennettu. Kaikki alla oleva on valinnaista.",
        Language.sv: "Tack, ditt svar har sparats. Allt nedan är valfritt.",
    },
    "tap_confirm": {
        Language.en: "Press Submit to save your answer.",
        Language.fi: "Tallenna vastauksesi painamalla Lähetä.",
        Language.sv: "Tryck på Skicka för att spara ditt svar.",
    },
    "tap_failed": {
        Language.en: "Your answer could not be saved yet. Press Submit to try again.",
        Language.fi: "Vastaustasi ei voitu vielä tallentaa. Yritä uudelleen painamalla Lähetä.",
        Language.sv: "Ditt svar kunde inte sparas ännu. Tryck på Skicka för att försöka igen.",
    },
    "comment": {
        Language.en: "Tell us more",
        Language.fi: "Kerro lisää",
        Language.sv: "Berätta mer",
    },
    "contact_me": {
        Language.en: "Contact me about this by email",
        Language.fi: "Ottakaa minuun yhteyttä tästä sähköpostitse",
        Language.sv: "Kontakta mig om detta via e-post",
    },
    "identified_notice": {
        Language.en: "Your answer is linked to your contact details with the sender.",
        Language.fi: "Vastauksesi yhdistetään yhteystietoihisi lähettäjän järjestelmässä.",
        Language.sv: "Ditt svar kopplas till dina kontaktuppgifter hos avsändaren.",
    },
    # Progress bar on the survey link page (#8); {answered} and {total} are numbers
    "progress_label": {
        Language.en: "Progress",
        Language.fi: "Edistyminen",
        Language.sv: "Framsteg",
    },
    "progress": {
        Language.en: "{answered} of {total} answered",
        Language.fi: "{answered}/{total} vastattu",
        Language.sv: "{answered} av {total} besvarade",
    },
    # One question at a time on the survey link page (#9); {n} and {total} are numbers
    "next": {
        Language.en: "Next",
        Language.fi: "Seuraava",
        Language.sv: "Nästa",
    },
    "previous": {
        Language.en: "Previous",
        Language.fi: "Edellinen",
        Language.sv: "Föregående",
    },
    "step": {
        Language.en: "Page {n} of {total}",
        Language.fi: "Sivu {n}/{total}",
        Language.sv: "Sida {n} av {total}",
    },
    "answer_this": {
        Language.en: "Please answer this question.",
        Language.fi: "Vastaa tähän kysymykseen.",
        Language.sv: "Svara på den här frågan.",
    },
    "answer_required": {
        Language.en: "Please answer every question that is not marked optional.",
        Language.fi: "Vastaa jokaiseen kysymykseen, jota ei ole merkitty valinnaiseksi.",
        Language.sv: "Svara på alla frågor som inte är märkta som valfria.",
    },
    "answer_not_valid": {
        Language.en: "Some answers could not be read. Please check them and send again.",
        Language.fi: "Joitakin vastauksia ei voitu lukea. Tarkista ne ja lähetä uudelleen.",
        Language.sv: "Några svar kunde inte läsas. Kontrollera dem och skicka igen.",
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
