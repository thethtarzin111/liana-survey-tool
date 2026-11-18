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
    channel: Literal["email", "link", "qr"] = "email"
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
