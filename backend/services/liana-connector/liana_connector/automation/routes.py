"""The Integrations page's API. Calls to Liana run outside the database transaction,
so a slow Liana never keeps a connection open."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from liana_survey_shared.config import get_settings
from liana_survey_shared.web.auth import CurrentUser, current_user
from liana_survey_shared.web.db import TenantDB, tenant_db

from . import domain, repo, secrets
from .client import AutomationClient, DemoLianaClient, LianaClient, LianaError
from .schemas import (
    Channel,
    Connection,
    ConnectionChanges,
    CredentialsIn,
    IntegrationsStatus,
    NewChannel,
    SyncEvent,
    TestEventIn,
)

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])

ClientFactory = Callable[[str, str, str], AutomationClient]


def client_factory() -> ClientFactory:
    """Builds the client for a host. Tests replace this dependency."""

    def build(host: str, client_id: str, secret: str) -> AutomationClient:
        if host == domain.DEMO_HOST:
            return DemoLianaClient(client_id, secret)
        return LianaClient(host, client_id, secret)

    return build


def demo_allowed() -> bool:
    return get_settings().auth_mode == "dev"


def _connection(row: dict[str, Any]) -> dict[str, Any]:
    return {**row, "settings": domain.merged_settings(row["settings"])}


def _event(row: dict[str, Any]) -> dict[str, Any]:
    return {**row, "contact": domain.masked_email(domain.contact_of(row["payload"]))}


def _saved(db: TenantDB) -> dict[str, Any]:
    with db() as conn:
        row = repo.get(conn)
    if row is None:
        raise HTTPException(404, "LianaAutomation is not connected")
    return row


def _client(row: dict[str, Any], build: ClientFactory, db: TenantDB) -> AutomationClient:
    try:
        secret = secrets.decrypt(row["secret_encrypted"], get_settings().integration_secret_key)
    except secrets.UnreadableSecret:
        message = "The saved secret can no longer be read. Enter the credentials again."
        with db() as conn:
            repo.update(conn, status="error", last_error=message)
        raise HTTPException(409, message) from None
    return build(row["host"], row["client_id"], secret)


@router.get("", response_model=IntegrationsStatus)
def integrations(db: TenantDB = Depends(tenant_db)) -> dict:
    """Card status for the Integrations page."""
    with db() as conn:
        row = repo.get(conn)
        counts = repo.event_counts(conn)
    return {
        "liana_automation": _connection(row) if row else None,
        "events": counts,
        "demo_available": demo_allowed(),
    }


@router.put("/liana-automation", response_model=Connection)
def save_credentials(
    body: CredentialsIn,
    db: TenantDB = Depends(tenant_db),
    user: CurrentUser = Depends(current_user),
) -> dict:
    """Wizard step 1. The secret is encrypted before it is stored and never returned."""
    try:
        host = domain.clean_host(body.host, demo_allowed())
    except domain.InvalidInput as error:
        raise HTTPException(422, str(error)) from None
    encrypted = hint = None
    if body.client_secret:
        encrypted = secrets.encrypt(body.client_secret, get_settings().integration_secret_key)
        hint = domain.secret_hint(body.client_secret)
    with db() as conn:
        existing = repo.get(conn)
        if existing is None and encrypted is None:
            raise HTTPException(422, "Enter the client secret.")
        settings = domain.merged_settings(existing["settings"] if existing else None)
        row = repo.save_credentials(
            conn, user.tenant_id, host, body.client_id.strip(), encrypted, hint, settings
        )
    return _connection(row)


@router.post("/liana-automation/test", response_model=Connection)
def test_connection(db: TenantDB = Depends(tenant_db), build=Depends(client_factory)) -> dict:
    """Wizard step 2: ping Liana. The result is the connection's status and last_error."""
    client = _client(_saved(db), build, db)
    try:
        client.ping()
        changes = {"status": "connected", "last_error": None}
    except LianaError as error:
        changes = {"status": "error", "last_error": str(error)}
    with db() as conn:
        return _connection(repo.update(conn, **changes))


@router.get("/liana-automation/channels", response_model=list[Channel])
def channels(db: TenantDB = Depends(tenant_db), build=Depends(client_factory)) -> list[dict]:
    """Wizard step 3: the account's channels."""
    try:
        return _client(_saved(db), build, db).channels()
    except LianaError as error:
        raise HTTPException(502, str(error)) from None


@router.post("/liana-automation/channels", response_model=Channel, status_code=201)
def create_channel(
    body: NewChannel, db: TenantDB = Depends(tenant_db), build=Depends(client_factory)
) -> dict:
    """Wizard step 3: create a channel, e.g. "Survey tool (test)"."""
    try:
        return _client(_saved(db), build, db).create_channel(body.name.strip())
    except LianaError as error:
        raise HTTPException(502, str(error)) from None


@router.patch("/liana-automation", response_model=Connection)
def change_connection(body: ConnectionChanges, db: TenantDB = Depends(tenant_db)) -> dict:
    """Wizard steps 3 and 4: the channel and the "what to send" switches."""
    with db() as conn:
        row = repo.get(conn)
        if row is None:
            raise HTTPException(404, "LianaAutomation is not connected")
        changes: dict[str, Any] = {}
        if body.channel_id is not None:
            changes["channel_id"] = body.channel_id
            changes["channel_name"] = body.channel_name or body.channel_id
        if body.settings is not None:
            changes["settings"] = domain.merged_settings(row["settings"], body.settings)
        if not changes:
            return _connection(row)
        return _connection(repo.update(conn, **changes))


def _send(event: dict[str, Any], db: TenantDB, build: ClientFactory) -> dict[str, Any]:
    """Send one stored event and record the attempt. A wrong host (404) also marks the
    connection as broken, so nothing more is sent until it is fixed."""
    row = _saved(db)
    if not row["channel_id"]:
        raise HTTPException(409, "Choose a channel first.")
    client = _client(row, build, db)
    status, error = "sent", None
    try:
        client.import_events(domain.import_body(row["channel_id"], [event["payload"]]))
    except LianaError as failure:
        status, error = "failed", str(failure)
        if failure.kind in ("config", "auth"):
            with db() as conn:
                repo.update(conn, status="error", last_error=error)
    with db() as conn:
        return _event(repo.finish_event(conn, event["id"], status, error))


@router.post("/liana-automation/test-event", response_model=SyncEvent, status_code=201)
def send_test_event(
    body: TestEventIn,
    db: TenantDB = Depends(tenant_db),
    user: CurrentUser = Depends(current_user),
    build=Depends(client_factory),
) -> dict:
    """Wizard step 5: a survey_answered event for a made-up @example.com contact."""
    try:
        email = domain.test_contact(body.email)
    except domain.InvalidInput as error:
        raise HTTPException(422, str(error)) from None
    if not _saved(db)["channel_id"]:
        raise HTTPException(409, "Choose a channel first.")
    payload = domain.test_event(email, datetime.now(UTC))
    with db() as conn:
        event = repo.add_event(conn, user.tenant_id, "survey_answered", payload, test=True)
    return _send(event, db, build)


@router.get("/liana-automation/events", response_model=list[SyncEvent])
def sync_log(
    status: Annotated[str | None, Query(pattern="^(pending|sent|retrying|failed)$")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    db: TenantDB = Depends(tenant_db),
) -> list[dict]:
    """The sync log, newest first."""
    with db() as conn:
        return [_event(row) for row in repo.events(conn, status, limit)]


@router.post("/events/{event_id}/retry", response_model=SyncEvent)
def retry_event(
    event_id: UUID, db: TenantDB = Depends(tenant_db), build=Depends(client_factory)
) -> dict:
    """Send a failed event again, with exactly the same data."""
    with db() as conn:
        event = repo.get_event(conn, event_id)
    if event is None:
        raise HTTPException(404, "Event not found")
    if event["status"] == "sent":
        raise HTTPException(409, "This event was already sent.")
    return _send(event, db, build)


@router.delete("/liana-automation", status_code=204)
def disconnect(db: TenantDB = Depends(tenant_db)) -> Response:
    """Forget the credentials and the channel. The sync log stays."""
    with db() as conn:
        if not repo.delete(conn):
            raise HTTPException(404, "LianaAutomation is not connected")
    return Response(status_code=204)
