"""Answer rules for the one-tap links (#42). Plain Python, no SQL or HTTP."""

from datetime import datetime

from liana_survey_shared.scoring import CSAT_SCALE, NPS_SCALE, THUMBS_SCALE

#: The main question of a thumbs, NPS or CSAT survey and the answers its buttons send.
SCALES = {"thumbs": THUMBS_SCALE, "nps": NPS_SCALE, "rating": CSAT_SCALE}


class AnswerProblem(Exception):
    """The link cannot be answered; the message is shown to the reader."""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


CLOSED = "This survey is closed and no longer takes answers."
FULL = "This survey has all the answers it needs. Thank you for wanting to answer."


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
        raise AnswerProblem(CLOSED, 410)
    if status != "live":
        raise AnswerProblem("This survey is not open yet.", 403)
    if full:
        raise AnswerProblem(FULL, 410)


def limit_reached(response_limit: int | None, response_count: int) -> bool:
    """True when the survey has as many readers as its response limit. A reader who
    already answered may still change their answer (#126), so check that next."""
    return response_limit is not None and response_count >= response_limit


def one_tap_answer(main_kind: str | None, raw: str | None) -> int:
    """The tapped answer to the main question, checked against its fixed scale."""
    scale = SCALES.get(main_kind or "")
    if scale is None:
        raise AnswerProblem("This answer link does not fit this survey.", 400)
    if raw is None or raw.strip() == "":
        raise AnswerProblem("Choose an answer in the email to answer this survey.", 400)
    try:
        value = int(raw.strip())
    except ValueError:
        value = None
    if value not in scale:
        raise AnswerProblem("This answer is not one of the choices.", 400)
    return value
