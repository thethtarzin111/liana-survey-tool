"""Request and response shapes for survey questions."""

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class QuestionKind(StrEnum):
    nps = "nps"
    rating = "rating"
    single_choice = "single_choice"
    multiple_choice = "multiple_choice"
    text = "text"


class QuestionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: QuestionKind
    prompt: str = ""
    options: list[str | int | float] = Field(default_factory=list)
    required: bool = True


class QuestionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: QuestionKind | None = None
    prompt: str | None = None
    options: list[str | int | float] | None = None
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
    options: list[str | int | float]
    required: bool
