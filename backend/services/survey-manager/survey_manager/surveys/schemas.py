"""Request and response shapes for /api/v1/surveys. Keep in sync with docs/api/openapi.yaml."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    computed_field,
    field_validator,
    model_validator,
)

DEFAULT_TITLE = "Untitled survey"

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
ThankYou = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


def _colour(value: str) -> str:
    from .branding import normalise_colour

    return normalise_colour(value)


#: "#2b6450" or "2B6450", stored as "#2B6450".
Colour = Annotated[str, AfterValidator(_colour)]


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
    # Branding: accent colour (buttons) and page background.
    accent_color: Colour | None = None
    background_color: Colour | None = None

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
    #: Branding (#66). The logo is uploaded separately; see logo_url.
    accent_color: str
    background_color: str
    logo_updated_at: datetime | None = Field(default=None, exclude=True)
    #: Publishing (#5). The token itself only appears inside public_url.
    link_token: str | None = Field(default=None, exclude=True)
    published_at: datetime | None = None
    language: str
    opens_at: datetime | None
    closes_at: datetime | None
    response_limit: int | None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def public_url(self) -> str | None:
        """The survey's public link once it has been published, e.g.
        https://survey.example.eu/r/Xq3...; answer links add the reader and answer."""
        if self.link_token is None:
            return None
        from liana_survey_shared.config import get_settings

        return f"{get_settings().public_base_url.rstrip('/')}/r/{self.link_token}"

    @computed_field
    @property
    def logo_url(self) -> str | None:
        """Where to load the logo from, or None when there is none. The version
        changes with every upload, so browsers never show an old logo."""
        if self.logo_updated_at is None:
            return None
        # Microseconds, so two uploads within the same second still get different URLs.
        version = int(self.logo_updated_at.timestamp() * 1_000_000)
        return f"/api/v1/surveys/{self.id}/logo?v={version}"


class Headline(BaseModel):
    """The Surveys list's "Headline score", e.g. "NPS +42" / "scale −100 to +100"."""

    score: str
    note: str


class SurveyListItem(Survey):
    """A survey as shown on the Surveys list."""

    answers: int  # submitted responses, from the worker's totals
    # Answers per value of the main question, from the worker's totals.
    distribution: dict[str, int] = Field(default_factory=dict, exclude=True)

    @computed_field
    @property
    def headline(self) -> Headline | None:
        """Score for thumbs, NPS and CSAT surveys once they have answers (#22)."""
        from liana_survey_shared.scoring import headline

        result = headline(self.type.value, self.distribution)
        return Headline(score=result.score, note=result.note) if result else None


class TestLinksRequest(BaseModel):
    """How many test answer links to make (local development only)."""

    model_config = ConfigDict(extra="forbid")

    count: Annotated[int, Field(ge=1, le=20)] = 3


class TestLinks(BaseModel):
    #: One per test reader; add &a=<answer> to answer the main question, e.g. &a=9.
    links: list[str]
