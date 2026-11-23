from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .domain import ReplyStatus, Status


class ContactRequest(BaseModel):
    id: UUID
    survey_id: UUID
    survey_title: str
    #: How to read `answer`: thumbs 0-2, nps 0-10, csat 1-5.
    survey_type: Literal["thumbs", "nps", "csat", "custom"]
    #: The reader's LianaMailer contact reference. Never an e-mail address.
    contact_ref: str
    #: The main question's value; None when the survey has no scale question.
    answer: int | None
    #: The reasons the reader picked, joined with "; ".
    reason: str | None
    segment: str
    status: Status
    #: Whether the request reached LianaAutomation (see docs/integrations.md).
    liana_status: Literal["pending", "sent", "failed"]
    created_at: datetime
    #: Whether the "You said, we did" message reached the connector's port; None
    #: until the request is resolved.
    reply_status: ReplyStatus | None
    reply_text: str | None
    resolved_at: datetime | None


class StatusCounts(BaseModel):
    all: int
    new: int
    contacted: int
    done: int


class ContactRequestList(BaseModel):
    items: list[ContactRequest]
    #: Per status, for the filter chips. Not narrowed by the status filter.
    counts: StatusCounts


class ContactRequestUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status


class ContactRequestResolve(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: The "You said, we did" message the reader gets. Trimmed.
    message: str = Field(min_length=1, max_length=1000)

    @field_validator("message", mode="before")
    @classmethod
    def _trim(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value
