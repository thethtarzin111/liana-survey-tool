"""Template rules, no SQL or HTTP."""

from typing import Any

from ..questions.domain import check_options
from ..questions.schemas import QuestionKind
from ..surveys.branding import DEFAULT_ACCENT, DEFAULT_BACKGROUND

ORGANISATION = "{organisation}"


class BuiltInTemplate(Exception):
    """Built-in templates are shared by every organisation, so nobody changes them."""

    def __init__(self) -> None:
        super().__init__("Built-in templates cannot be changed.")


class NoQuestions(Exception):
    def __init__(self) -> None:
        super().__init__("Add a question before you save the survey as a template.")


def personalise(text: str, organisation: str) -> str:
    """Put the organisation's name into template text such as
    "How likely are you to recommend {organisation} to a friend or colleague?"."""
    return text.replace(ORGANISATION, organisation)


def template_for(template: dict[str, Any], organisation: str) -> dict[str, Any]:
    """A template as the organisation sees it."""
    return {
        **template,
        "questions": [
            {
                "kind": q["kind"],
                "prompt": personalise(q.get("prompt", ""), organisation),
                "options": q.get("options", []),
                "required": q.get("required", True),
            }
            for q in template["questions"]
        ],
    }


def survey_questions(template: dict[str, Any], organisation: str) -> list[dict[str, Any]]:
    """The questions a new survey gets from a template, checked like any other question."""
    questions = template_for(template, organisation)["questions"]
    for question in questions:
        question["options"] = check_options(QuestionKind(question["kind"]), question["options"])
    return questions


def survey_colours(template: dict[str, Any]) -> tuple[str, str]:
    """The accent and background colours of a survey made from a template. Own
    templates keep the colours of the survey they were saved from; built-in ones
    have none, so their surveys get the defaults."""
    return (
        template.get("accent_color") or DEFAULT_ACCENT,
        template.get("background_color") or DEFAULT_BACKGROUND,
    )


def check_own(template: dict[str, Any]) -> None:
    """Only the organisation's own templates can be renamed or deleted."""
    if not template["own"]:
        raise BuiltInTemplate()


def saved_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A survey's questions as a template keeps them, in order. A template needs one."""
    if not questions:
        raise NoQuestions()
    return [
        {
            "kind": q["kind"],
            "prompt": q["prompt"],
            "options": q["options"],
            "required": q["required"],
        }
        for q in questions
    ]
