"""Queue message formats. These are a contract between services: change them
with care and update docs/integrations.md."""

import re
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

_SEGMENT = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")
# The Results API uses these as filter values for "No segment" and "Other".
RESERVED_SEGMENTS = ("none", "other")


def is_valid_segment(value: str) -> bool:
    """A segment tag from a link: lowercase letters, digits and hyphens, not reserved."""
    return _SEGMENT.fullmatch(value) is not None and value not in RESERVED_SEGMENTS


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
    segment: str = "all"
    channel: Literal["email", "link", "qr"] = "link"
    answers: list[AnswerValue]
    # Only set in identified mode, after the respondent opted in.
    contact_ref: str | None = None

    @field_validator("segment")
    @classmethod
    def _segment_is_valid(cls, value: str) -> str:
        if not is_valid_segment(value):
            raise ValueError("invalid segment")
        return value


class ContactRequested(Message):
    """Sent by the worker when a respondent ticks "Contact me".
    The Liana connector forwards it to LianaAutomation (POST /import)."""

    type: Literal["contact.requested"] = "contact.requested"
    survey_id: UUID
    contact_request_id: UUID
    contact_ref: str


class ContactResolved(Message):
    """Sent by survey-manager when the team resolves a contact request. The
    Liana connector passes the team's "You said, we did" message on to the
    reader, known only by their contact reference."""

    type: Literal["contact.resolved"] = "contact.resolved"
    survey_id: UUID
    contact_request_id: UUID
    contact_ref: str
    message: str = Field(min_length=1, max_length=1000)


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
