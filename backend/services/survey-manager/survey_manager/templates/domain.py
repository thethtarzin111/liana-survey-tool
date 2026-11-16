"""Template rules, no SQL or HTTP."""

from typing import Any

from ..questions.domain import check_options
from ..questions.schemas import QuestionKind

ORGANISATION = "{organisation}"


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
