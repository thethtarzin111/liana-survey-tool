"""Answer rules for the one-tap links (#42). Plain Python, no SQL or HTTP."""

from liana_survey_shared.scoring import CSAT_SCALE, NPS_SCALE, THUMBS_SCALE

#: The main question of a thumbs, NPS or CSAT survey and the answers its buttons send.
SCALES = {"thumbs": THUMBS_SCALE, "nps": NPS_SCALE, "rating": CSAT_SCALE}


class AnswerProblem(Exception):
    """The link cannot be answered; the message is shown to the reader."""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def check_open(status: str) -> None:
    """Only live surveys take answers."""
    if status == "closed":
        raise AnswerProblem("This survey is closed and no longer takes answers.", 410)
    if status != "live":
        raise AnswerProblem("This survey is not open yet.", 403)


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
