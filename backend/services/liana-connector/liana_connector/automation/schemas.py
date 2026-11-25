from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SendSettings(BaseModel):
    answers: bool
    contact_requests: bool
    themes: bool


class Connection(BaseModel):
    host: str
    auth_type: Literal["oauth"]
    client_id: str
    #: The last 4 characters of the secret; empty for short secrets.
    secret_hint: str
    channel_id: str | None
    channel_name: str | None
    settings: SendSettings
    status: Literal["disconnected", "connected", "error"]
    last_error: str | None
    updated_at: datetime


class IntegrationsStatus(BaseModel):
    liana_automation: Connection | None
    #: Events in the sync log by status.
    events: dict[str, int]
    #: Whether the built-in demo host may be used (local development only).
    demo_available: bool
    #: Whether the server has the LianaMailer API settings, needed to send events for
    #: newsletter readers (their email address is looked up there).
    lianamailer_set_up: bool = False


class CredentialsIn(BaseModel):
    host: str = Field(max_length=200)
    client_id: str = Field(min_length=1, max_length=200)
    #: Required the first time; left out to keep the saved secret.
    client_secret: str | None = Field(default=None, min_length=1, max_length=500)


class ConnectionChanges(BaseModel):
    channel_id: str | None = Field(default=None, max_length=100)
    channel_name: str | None = Field(default=None, max_length=200)
    settings: dict[str, bool] | None = None


class Channel(BaseModel):
    id: str
    name: str


class NewChannel(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class TestEventIn(BaseModel):
    email: str | None = Field(default=None, max_length=120)


class SyncEvent(BaseModel):
    id: UUID
    verb: str
    #: Shortened, e.g. "su…@example.com".
    contact: str | None
    test: bool
    #: skipped: deliberately not sent; last_error says why (anonymous, unknown contact).
    status: Literal["pending", "sent", "retrying", "failed", "skipped"]
    attempts: int
    last_error: str | None
    #: What was (or will be) sent to POST /import, and LianaAutomation's answer
    #: (HTTP status and body), for the sync log's Details.
    payload: dict[str, Any]
    liana_response: str | None = None
    created_at: datetime
    sent_at: datetime | None
