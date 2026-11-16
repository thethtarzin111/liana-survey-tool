"""Request and response shapes for survey questions. Keep in sync with docs/api/openapi.yaml.

The answer-type rules themselves live in domain.py."""

from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

PROMPT_MAX_LENGTH = 500

Prompt = Annotated[str, StringConstraints(strip_whitespace=True, max_length=PROMPT_MAX_LENGTH)]


class QuestionKind(StrEnum):
    """Answer types, with the prototype's "Answer type" label for each."""

    single_choice = "single_choice"  # Multiple choice (pick one)
    multiple_choice = "multiple_choice"  # Checkboxes (pick any)
    dropdown = "dropdown"  # Dropdown (pick one)
    text = "text"  # Short answer
    long_text = "long_text"  # Paragraph
    rating = "rating"  # Rating 1-5 (CSAT)
    nps = "nps"  # NPS 0-10
    reasons = "reasons"  # Reason bubbles (pick any; each becomes a Top reasons category)


class QuestionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: QuestionKind
    prompt: Prompt = ""
    options: list[Any] = Field(default_factory=list)
    required: bool = True

    @model_validator(mode="after")
    def options_fit_the_kind(self):
        from .domain import check_options

        self.options = check_options(self.kind, self.options)
        return self


class QuestionUpdate(BaseModel):
    """Fields left out stay the same. The type and options are checked together in
    the route, against the stored question (see domain.options_after_change)."""

    model_config = ConfigDict(extra="forbid")

    kind: QuestionKind | None = None
    prompt: Prompt | None = None
    options: list[Any] | None = None
    required: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def no_nulls(cls, data: Any) -> Any:
        if isinstance(data, dict):
            nulls = sorted(key for key, value in data.items() if value is None)
            if nulls:
                raise ValueError(f"{', '.join(nulls)} cannot be null; leave the field out instead")
        return data


class QuestionOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_ids: list[UUID]

    @model_validator(mode="after")
    def ids_are_unique(self):
        if len(self.question_ids) != len(set(self.question_ids)):
            raise ValueError("question_ids must not contain duplicates")
        return self


class Question(BaseModel):
    id: UUID
    survey_id: UUID
    position: int
    kind: QuestionKind
    prompt: str
    options: list[str]
    required: bool
