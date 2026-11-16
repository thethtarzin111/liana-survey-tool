"""Response shapes for /api/v1/templates. Keep in sync with docs/api/openapi.yaml."""

from uuid import UUID

from pydantic import BaseModel

from ..questions.schemas import QuestionKind
from ..surveys.schemas import SurveyType


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
    #: The first one is the main question; thumbs, NPS and CSAT templates follow it
    #: with optional reason bubbles.
    questions: list[TemplateQuestion]
