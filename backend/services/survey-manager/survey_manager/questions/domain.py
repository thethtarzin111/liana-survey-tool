"""Answer-type rules for questions: what each type needs and which answers it accepts.

Plain Python, no SQL or HTTP, so a later PHP port can copy it directly.
The prototype's "Answer type" labels are next to each kind in QuestionKind.
"""

from typing import Any

from .schemas import QuestionKind

#: Types whose answers are picked from the question's own options.
CHOICE_KINDS = frozenset(
    {
        QuestionKind.single_choice,
        QuestionKind.multiple_choice,
        QuestionKind.dropdown,
        QuestionKind.reasons,
    }
)
#: Types where more than one option may be picked.
MULTI_KINDS = frozenset({QuestionKind.multiple_choice, QuestionKind.reasons})
#: Fixed scales. They cannot be changed, so results stay comparable.
SCALES = {QuestionKind.rating: range(1, 6), QuestionKind.nps: range(0, 11)}
#: Longest accepted free-text answer per type.
TEXT_LIMITS = {QuestionKind.text: 500, QuestionKind.long_text: 5000}

MAX_OPTIONS = 20
OPTION_MAX_LENGTH = 200


class QuestionRuleError(ValueError):
    """The question's type and options do not fit together."""


class AnswerError(ValueError):
    """An answer does not fit its question."""


def check_options(kind: QuestionKind, options: list[Any]) -> list[str]:
    """Return the options to store for `kind`, or raise QuestionRuleError.

    Choice types need 1-20 distinct, non-blank texts (spaces trimmed).
    Text and scale types have no options."""
    if kind not in CHOICE_KINDS:
        if options:
            raise QuestionRuleError(f"{kind.value} questions have no options")
        return []
    if not options:
        raise QuestionRuleError(f"{kind.value} questions need at least one option")
    if len(options) > MAX_OPTIONS:
        raise QuestionRuleError(f"a question can have at most {MAX_OPTIONS} options")
    cleaned: list[str] = []
    for option in options:
        if not isinstance(option, str) or not option.strip():
            raise QuestionRuleError("options must be non-empty text")
        text = option.strip()
        if len(text) > OPTION_MAX_LENGTH:
            raise QuestionRuleError(f"an option can be at most {OPTION_MAX_LENGTH} characters")
        if text.casefold() in (seen.casefold() for seen in cleaned):
            raise QuestionRuleError(f'option "{text}" is listed twice')
        cleaned.append(text)
    return cleaned


def options_after_change(
    old_kind: QuestionKind,
    old_options: list[Any],
    new_kind: QuestionKind,
    new_options: list[Any] | None,
) -> list[str]:
    """Options after an edit. Options left out of the edit stay as they were,
    except that switching to a type without options clears them."""
    if new_options is None:
        new_options = old_options if new_kind in CHOICE_KINDS else []
    return check_options(new_kind, new_options)


def check_answer(
    kind: QuestionKind, options: list[str], required: bool, value: Any
) -> str | int | list[str] | None:
    """Return the answer to store, or raise AnswerError. None means "not answered".

    Choice answers are option texts; scale answers are whole numbers; text is trimmed."""
    if value is None or value == "" or value == []:
        if required:
            raise AnswerError("this question needs an answer")
        return None

    if kind in SCALES:
        scale = SCALES[kind]
        if isinstance(value, bool) or not isinstance(value, int) or value not in scale:
            raise AnswerError(f"pick a whole number from {scale.start} to {scale.stop - 1}")
        return value

    if kind in TEXT_LIMITS:
        if not isinstance(value, str):
            raise AnswerError("the answer must be text")
        text = value.strip()
        if not text:
            return check_answer(kind, options, required, None)
        if len(text) > TEXT_LIMITS[kind]:
            raise AnswerError(f"the answer can be at most {TEXT_LIMITS[kind]} characters")
        return text

    if kind in MULTI_KINDS:
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise AnswerError("pick one or more of the options")
        if len(set(value)) != len(value):
            raise AnswerError("each option can be picked only once")
        if unknown := [item for item in value if item not in options]:
            raise AnswerError(f'"{unknown[0]}" is not one of the options')
        return value

    # single_choice and dropdown
    if not isinstance(value, str):
        raise AnswerError("pick one of the options")
    if value not in options:
        raise AnswerError(f'"{value}" is not one of the options')
    return value
