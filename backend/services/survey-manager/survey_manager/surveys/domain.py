"""Plain survey rules, no SQL or HTTP. Keeping them here keeps a later PHP port simple."""

import secrets

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
