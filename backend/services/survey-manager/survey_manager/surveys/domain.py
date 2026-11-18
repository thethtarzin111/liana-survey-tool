"""Plain survey rules, no SQL or HTTP. Keeping them here keeps a later PHP port simple."""

import html
import re
import secrets
import unicodedata

from .schemas import TITLE_MAX, SurveyStatus, Title

# Which statuses each list action may start from, and where it leads.
CLOSE_FROM = frozenset({SurveyStatus.live})
UNPUBLISH_FROM = frozenset({SurveyStatus.live, SurveyStatus.scheduled})

#: The main question each template type needs before it can be published.
MAIN_QUESTION_KIND = {"thumbs": "thumbs", "nps": "nps", "csat": "rating"}

COPY_SUFFIX = " (copy)"


class StatusChangeNotAllowed(Exception):
    """The survey's current status does not allow this action."""

    def __init__(self, action: str, current: SurveyStatus):
        super().__init__(f"A {current.value} survey cannot be {action}.")


class NotReadyToPublish(Exception):
    """The draft is missing something readers need."""


def published_status(
    current: SurveyStatus, survey_type: str, questions: list[tuple[str, str]]
) -> SurveyStatus:
    """Publishing makes a draft live. It needs questions (kind, prompt) in order, and
    thumbs, NPS and CSAT surveys need their main question first (it is what the
    email buttons answer). Every question needs its text; reason bubbles have none."""
    if current is not SurveyStatus.draft:
        raise StatusChangeNotAllowed("published", current)
    if not questions:
        raise NotReadyToPublish("Add a question before publishing.")
    main = MAIN_QUESTION_KIND.get(survey_type)
    if main and questions[0][0] != main:
        raise NotReadyToPublish("Add the survey's main question before publishing.")
    for number, (kind, prompt) in enumerate(questions, start=1):
        if kind != "reasons" and not prompt.strip():
            if main and number == 1:
                raise NotReadyToPublish("Write the survey's main question before publishing.")
            raise NotReadyToPublish(f"Question {number} has no text. Write it or delete it first.")
    return SurveyStatus.live


def new_link_token() -> str:
    """A random, hard-to-guess public token (22 URL-safe characters, 128 bits)."""
    return secrets.token_urlsafe(16)


def closed_status(current: SurveyStatus) -> SurveyStatus:
    """Closing stops a live survey from taking answers."""
    if current not in CLOSE_FROM:
        raise StatusChangeNotAllowed("closed", current)
    return SurveyStatus.closed


def unpublished_status(current: SurveyStatus) -> SurveyStatus:
    """Unpublishing turns a live or scheduled survey back into a draft."""
    if current not in UNPUBLISH_FROM:
        raise StatusChangeNotAllowed("unpublished", current)
    return SurveyStatus.draft


def copy_title(title: Title) -> str:
    """Title of a duplicated survey, kept within the title limit."""
    return title[: TITLE_MAX - len(COPY_SUFFIX)].rstrip() + COPY_SUFFIX


# --- Newsletter snippet (#40) -------------------------------------------------------

#: One-tap answers per survey type: (value in the link, button text), as in the prototype.
SNIPPET_ANSWERS: dict[str, list[tuple[int, str]]] = {
    "thumbs": [(0, "Not for me"), (1, "Good"), (2, "Loved it")],
    "nps": [(n, str(n)) for n in range(11)],
    "csat": [(n, str(n)) for n in range(1, 6)],
}
SNIPPET_FOOTER = "One tap. Anonymous unless you ask to be contacted."


def campaign_tag(title: str) -> str:
    """The default campaign tag: the survey name as a slug, e.g. "member-nps-2026"
    (the "Tag …" shown for live surveys in the list). Keep in sync with the
    frontend's src/utils/slug.ts."""
    plain = "".join(
        c for c in unicodedata.normalize("NFKD", title) if not unicodedata.combining(c)
    )  # ä → a, é → e (as slug() in the frontend)
    tag = re.sub(r"[^a-z0-9]+", "-", plain.strip().lower()).strip("-")[:40].strip("-")
    return tag or "campaign"


class NoSnippet(Exception):
    """The survey cannot be answered from an email (yet)."""


def check_snippet(survey_type: str, status: SurveyStatus, question: str | None) -> None:
    """Raise NoSnippet unless the survey can be answered from a newsletter."""
    if status is not SurveyStatus.live:
        raise NoSnippet("Publish the survey first.")
    if survey_type not in SNIPPET_ANSWERS:
        raise NoSnippet("Custom surveys can't be answered from an email yet.")
    if not question:
        raise NoSnippet("Write the survey's main question first.")


def snippet_html(survey_type: str, status: SurveyStatus, question: str | None, link: str) -> str:
    """The HTML block for a LianaMailer newsletter: the main question and one link
    per answer. Plain tables and inline styles, as email clients need; `link` is
    the snippet link without the answer."""
    check_snippet(survey_type, status, question)
    answers = SNIPPET_ANSWERS[survey_type]
    padding = {"nps": "10px 13px", "thumbs": "14px 20px"}.get(survey_type, "12px 18px")
    cells = [
        f'<td align="center" style="padding:4px"><a href="{html.escape(f"{link}&a={value}")}" '
        f'style="display:inline-block;padding:{padding};border:2px solid #353A40;'
        "border-radius:999px;background:#FFFFFF;color:#353A40;"
        f'font:bold 16px Arial,sans-serif;text-decoration:none">{html.escape(label)}</a></td>'
        for value, label in answers
    ]
    return "\n".join(
        [
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">',
            '<tr><td align="center" style="padding:24px 0 8px;font:bold 20px Arial,sans-serif;'
            f'color:#353A40">{html.escape(question)}</td></tr>',
            '<tr><td align="center">'
            '<table role="presentation" cellpadding="0" cellspacing="0"><tr>',
            *cells,
            "</tr></table></td></tr>",
            '<tr><td align="center" style="padding:8px;font:12px Arial,sans-serif;'
            f'color:#5F6267">{SNIPPET_FOOTER}</td></tr>',
            "</table>",
        ]
    )
