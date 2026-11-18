"""Queue message formats. These are a contract between services: change them
with care and update docs/integrations.md."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Message(BaseModel):
    message_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tenant_id: UUID


class AnswerValue(BaseModel):
    question_id: UUID
    number: float | None = None
    text: str | None = None
    choices: list[str] | None = None


class AnswerSubmitted(Message):
    """Sent by the respondent endpoint, saved by the worker."""

    type: Literal["answer.submitted"] = "answer.submitted"
    survey_id: UUID
    # Hash of the signed link token, so the same link is not counted twice.
    link_token_hash: str
    segment: str = Field(default="all", pattern=r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")
    channel: Literal["email", "link", "qr"] = "link"
    answers: list[AnswerValue]
    # Only set in identified mode, after the respondent opted in.
    contact_ref: str | None = None


class ContactRequested(Message):
    """Sent by the worker when a respondent ticks "Contact me".
    The Liana connector forwards it to LianaAutomation (POST /import)."""

    type: Literal["contact.requested"] = "contact.requested"
    survey_id: UUID
    contact_request_id: UUID
    contact_ref: str


class NewResponsesDigest(Message):
    """Sent by the worker when a survey's owner is due an email about new
    responses. The Liana connector sends it through its notification mail port.

    Counts and a link only: never answers or anything about the readers. The
    recipient is the app user who created the survey, not a reader."""

    type: Literal["responses.digest"] = "responses.digest"
    survey_id: UUID
    survey_title: str
    # Responses since the previous email, and all responses so far.
    new_responses: int = Field(gt=0)
    total_responses: int = Field(ge=0)
    results_url: str
    recipient_email: str
    recipient_name: str
