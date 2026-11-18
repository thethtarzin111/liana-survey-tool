"""Answer rules for the one-tap links (#42). Plain Python, no SQL or HTTP."""

from datetime import datetime

from liana_survey_shared.scoring import CSAT_SCALE, NPS_SCALE, THUMBS_SCALE
from liana_survey_shared.texts import text

#: The main question of a thumbs, NPS or CSAT survey and the answers its buttons send.
SCALES = {"thumbs": THUMBS_SCALE, "nps": NPS_SCALE, "rating": CSAT_SCALE}


class AnswerProblem(Exception):
    """The link cannot be answered. `key` names the fixed text shown to the reader
    (liana_survey_shared.texts); the exception's message is its English version."""

    def __init__(self, key: str, status_code: int):
        super().__init__(text(key))
        self.key = key
        self.status_code = status_code

    def message(self, language: str | None) -> str:
        """The text for the reader, in the survey's language."""
        return text(self.key, language)


def check_open(
    status: str,
    *,
    closes_at: datetime | None = None,
    now: datetime | None = None,
    full: bool = False,
) -> None:
    """Only live surveys take answers: not after their close date (#47), and not
    from new readers once the response limit is reached (`full`)."""
    if status == "closed" or (closes_at is not None and now is not None and now >= closes_at):
        raise AnswerProblem("closed", 410)
    if status != "live":
        raise AnswerProblem("not_open", 403)
    if full:
        raise AnswerProblem("full", 410)


def limit_reached(response_limit: int | None, response_count: int) -> bool:
    """True when the survey has as many readers as its response limit. A reader who
    already answered may still change their answer (#126), so check that next."""
    return response_limit is not None and response_count >= response_limit


def one_tap_answer(main_kind: str | None, raw: str | None) -> int:
    """The tapped answer to the main question, checked against its fixed scale."""
    scale = SCALES.get(main_kind or "")
    if scale is None:
        raise AnswerProblem("wrong_survey", 400)
    if raw is None or raw.strip() == "":
        raise AnswerProblem("no_answer", 400)
    try:
        value = int(raw.strip())
    except ValueError:
        value = None
    if value not in scale:
        raise AnswerProblem("not_a_choice", 400)
    return value
