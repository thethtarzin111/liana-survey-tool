"""Request and response shapes for /api/v1/templates. Keep in sync with docs/api/openapi.yaml."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from ..questions.schemas import QuestionKind
from ..surveys.schemas import Description, SurveyType, Title


class TemplateQuestion(BaseModel):
    kind: QuestionKind
    prompt: str
    options: list[str] = []
    required: bool = True


class Template(BaseModel):
    id: UUID
    name: str
    type: SurveyType
    description: str
    thank_you: str
    #: Shown as a card on the Templates page.
    featured: bool
    #: Saved by the organisation. Built-in templates are read-only.
    own: bool
    #: The first one is the main question; thumbs, NPS and CSAT templates follow it
    #: with optional reason bubbles.
    questions: list[TemplateQuestion]
    #: Branding colours of the survey an own template was saved from; None for built-in ones.
    accent_color: str | None = None
    background_color: str | None = None


class TemplateCreate(BaseModel):
    """Save a survey as a template: its type, questions, thank-you message and colours."""

    model_config = ConfigDict(extra="forbid")

    survey_id: UUID
    name: Title
    description: Description = ""


class TemplateUpdate(BaseModel):
    """Rename a template or change its description. Omitted fields stay as they are."""

    model_config = ConfigDict(extra="forbid")

    name: Title | None = None
    description: Description | None = None

    @model_validator(mode="before")
    @classmethod
    def no_nulls(cls, data: Any) -> Any:
        if isinstance(data, dict):
            nulls = sorted(k for k, v in data.items() if v is None)
            if nulls:
                raise ValueError(f"{', '.join(nulls)} cannot be null; leave the field out instead")
        return data
