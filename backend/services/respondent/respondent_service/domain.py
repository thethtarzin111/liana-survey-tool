"""Answer rules for the one-tap links (#42) and the survey link page (#105).
Plain Python, no SQL or HTTP."""

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from liana_survey_shared.messages import AnswerValue
from liana_survey_shared.scoring import CSAT_SCALE, NPS_SCALE, THUMBS_SCALE
from liana_survey_shared.texts import text

#: The main question of a thumbs, NPS or CSAT survey and the answers its buttons send.
SCALES = {"thumbs": THUMBS_SCALE, "nps": NPS_SCALE, "rating": CSAT_SCALE}
#: Picked from the question's own options; more than one may be picked for the last two.
CHOICE_KINDS = frozenset({"single_choice", "dropdown", "multiple_choice", "reasons"})
MULTI_KINDS = frozenset({"multiple_choice", "reasons"})
#: Longest free-text answer per kind, as survey-manager allows (questions/domain.py).
TEXT_LIMITS = {"text": 500, "long_text": 5000}
#: "Not for me": the only thumbs answer that asks for reasons (as in the email flow).
THUMBS_NOT_FOR_ME = 0


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


def field_name(question: Mapping[str, Any]) -> str:
    """The form field of a question on the survey link page."""
    return f"q-{question['id']}"


def asks_reasons(survey_type: str, question: Mapping[str, Any], main_answer: str | None) -> bool:
    """Thumbs surveys ask their reasons only after "Not for me"; other surveys always do."""
    if survey_type != "thumbs" or question["kind"] != "reasons":
        return True
    return main_answer == str(THUMBS_NOT_FOR_ME)


def form_answers(
    survey_type: str,
    questions: Sequence[Mapping[str, Any]],
    form: Mapping[str, Sequence[str]],
) -> list[AnswerValue]:
    """The answers sent from the survey link page, checked against each question.

    `form` holds the values sent per field (see field_name). Blank values count
    as not answered, so the list is empty when every question is optional and
    left blank. Raises AnswerProblem "answer_required" when a required question
    is left blank, and "answer_not_valid" for answers that are not one of the
    question's choices or too long."""
    main_answer = None
    if questions:
        sent = [v.strip() for v in form.get(field_name(questions[0]), ())]
        main_answer = sent[0] if len(sent) == 1 else None
    answers: list[AnswerValue] = []
    for question in questions:
        if not asks_reasons(survey_type, question, main_answer):
            continue
        values = [v.strip() for v in form.get(field_name(question), ()) if v.strip()]
        if not values:
            if question["required"]:
                raise AnswerProblem("answer_required", 400)
            continue
        answers.append(_answer(question, values))
    return answers


def _answer(question: Mapping[str, Any], values: list[str]) -> AnswerValue:
    kind = question["kind"]
    answer = AnswerValue(question_id=question["id"])
    if kind in SCALES:
        if len(values) != 1 or not values[0].isdigit() or int(values[0]) not in SCALES[kind]:
            raise AnswerProblem("answer_not_valid", 400)
        answer.number = int(values[0])
    elif kind in TEXT_LIMITS:
        if len(values) != 1 or len(values[0]) > TEXT_LIMITS[kind]:
            raise AnswerProblem("answer_not_valid", 400)
        answer.text = values[0]
    elif kind in CHOICE_KINDS:
        picked = list(dict.fromkeys(values))
        if any(v not in question["options"] for v in picked):
            raise AnswerProblem("answer_not_valid", 400)
        if kind not in MULTI_KINDS and len(picked) != 1:
            raise AnswerProblem("answer_not_valid", 400)
        answer.choices = picked
    else:
        raise AnswerProblem("answer_not_valid", 400)
    return answer
