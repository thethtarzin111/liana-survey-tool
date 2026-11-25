"""Queue message formats. These are a contract between services: change them
with care and update docs/integrations.md."""

import re
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

_SEGMENT = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")
# The Results API uses these as filter values for "No segment" and "Other".
RESERVED_SEGMENTS = ("none", "other")


_CAMPAIGN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")


def is_valid_campaign(value: str) -> bool:
    """A campaign tag from a link: lowercase letters, digits and hyphens."""
    return _CAMPAIGN.fullmatch(value) is not None


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
    # The LianaMailer contact id from a newsletter link (r=): the answer is identified
    # (liana_survey_shared.contact). None for the public link and the QR code.
    contact_ref: str | None = None
    # The "Tell us more" box, for surveys without a text question of their own.
    comment: str | None = Field(default=None, max_length=5000)
    # The reader ticked "Contact me about this by email" (needs a contact_ref or a
    # contact_email).
    contact_me: bool = False
    # Public page only: the address a reader who ticked "Contact me" typed. Readers
    # from a newsletter link have a contact_ref instead.
    contact_email: str | None = Field(default=None, max_length=254)
    # The follow-up page saving the tapped answer alone (step=tap): it replaces only
    # the answers in this message, so the reader's earlier follow-up answers stay.
    main_only: bool = False
    # The newsletter's campaign tag from the link (c=), passed on to LianaAutomation.
    campaign: str | None = None

    @field_validator("segment")
    @classmethod
    def _segment_is_valid(cls, value: str) -> str:
        if not is_valid_segment(value):
            raise ValueError("invalid segment")
        return value

    @field_validator("campaign")
    @classmethod
    def _campaign_is_valid(cls, value: str | None) -> str | None:
        if value is not None and not is_valid_campaign(value):
            raise ValueError("invalid campaign")
        return value


class AnswerRecorded(Message):
    """Sent by the worker each time it saves or changes an answer. The Liana
    connector sends it to LianaAutomation as a survey_answered event when the
    organisation connected it and the answer has a contact; otherwise the sync log
    says why it was not sent. Never the answers' texts."""

    type: Literal["answer.recorded"] = "answer.recorded"
    survey_id: UUID
    response_id: UUID
    survey_title: str
    # The main question's kind (nps, rating, thumbs) and the reader's answer to it.
    main_kind: str | None = None
    score: int | None = None
    campaign: str | None = None
    # None for anonymous answers.
    contact_ref: str | None = None


class ContactRequested(Message):
    """Sent by the worker when a respondent ticks "Contact me".
    The Liana connector forwards it to LianaAutomation (POST /import)."""

    type: Literal["contact.requested"] = "contact.requested"
    survey_id: UUID
    contact_request_id: UUID
    # Who asked: the LianaMailer contact id (newsletter link) or the address typed on
    # the public page. At least one of them.
    contact_ref: str | None = None
    contact_email: str | None = None
    # The response the request belongs to; the connector stores the contact's email
    # address on it once LianaMailer gave it.
    response_id: UUID | None = None

    @model_validator(mode="after")
    def _has_a_contact(self) -> "ContactRequested":
        if not (self.contact_ref or self.contact_email):
            raise ValueError("a contact request needs contact_ref or contact_email")
        return self


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
