"""Request and response shapes for /api/v1/surveys. Keep in sync with docs/api/openapi.yaml."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    StrictBool,
    StringConstraints,
    field_validator,
    model_validator,
)

DEFAULT_TITLE = "Untitled survey"

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
ThankYou = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


class SurveyType(StrEnum):
    """What the survey finds out. Matches the first wizard step in the prototype."""

    thumbs = "thumbs"  # Thumbs rating: was it useful?
    nps = "nps"  # Net Promoter Score, 0-10
    csat = "csat"  # Customer satisfaction, 1-5
    custom = "custom"  # Start from scratch


class SurveyStatus(StrEnum):
    draft = "draft"
    scheduled = "scheduled"
    live = "live"
    closed = "closed"


class SurveyCreate(BaseModel):
    # tenant_id, status and created_by come from the server, never from the client.
    model_config = ConfigDict(extra="forbid")

    type: SurveyType
    title: Title = DEFAULT_TITLE
    description: Description | None = None

    @field_validator("description", mode="before")
    @classmethod
    def empty_description_is_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class SurveyUpdate(BaseModel):
    """Fields that can change. Omitted fields stay as they are.

    Sending a field as null is an error (422), not a silent no-op: title and
    type can never be empty.
    """

    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    description: Description | None = None
    thank_you: ThankYou | None = None
    type: SurveyType | None = None
    # Reader options (true or false only, not "yes" or 1).
    comment_field: StrictBool | None = None
    show_results: StrictBool | None = None
    contact_opt_in: StrictBool | None = None

    @field_validator("description", "thank_you", mode="before")
    @classmethod
    def empty_description_is_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="before")
    @classmethod
    def no_nulls(cls, data: Any) -> Any:
        if isinstance(data, dict):
            nulls = sorted(k for k, v in data.items() if v is None)
            if nulls:
                raise ValueError(f"{', '.join(nulls)} cannot be null; leave the field out instead")
        return data


class Survey(BaseModel):
    id: UUID
    title: str
    description: str | None
    thank_you: str | None  # shown to readers after answering
    type: SurveyType
    status: SurveyStatus
    anonymous: bool
    #: Reader options: "Tell us more" field, results after answering, contact opt-in.
    comment_field: bool
    show_results: bool
    contact_opt_in: bool
    language: str
    opens_at: datetime | None
    closes_at: datetime | None
    response_limit: int | None
    created_at: datetime
    updated_at: datetime


class SurveyListItem(Survey):
    """A survey as shown on the Surveys list."""

    answers: int  # submitted responses, from the worker's totals
