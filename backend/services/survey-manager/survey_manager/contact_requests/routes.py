"""Contact request endpoints: /api/v1/contact-requests."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool

from liana_survey_shared.messages import ContactResolved
from liana_survey_shared.web.auth import CurrentUser, current_user
from liana_survey_shared.web.db import TenantDB, tenant_db

from ..liana_events import LianaEvents, get_liana_events
from . import domain, repo
from .domain import Status
from .schemas import (
    ContactRequest,
    ContactRequestList,
    ContactRequestResolve,
    ContactRequestUpdate,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/contact-requests", tags=["contact requests"])

NOT_FOUND = "Contact request not found"
NOT_QUEUED = "Marked as done, but the message to the reader could not be sent. Try again."


@router.get("", response_model=ContactRequestList)
def list_contact_requests(
    status_filter: Annotated[Status | None, Query(alias="status")] = None,
    survey_id: UUID | None = None,
    db: TenantDB = Depends(tenant_db),
) -> dict:
    """Readers who ticked "Contact me", newest first. Filter by `status` and
    `survey_id`. `counts` covers every status of the chosen survey (or all)."""
    with db() as conn:
        items = repo.list_all(conn, status_filter, survey_id)
        counts = domain.counts(repo.status_counts(conn, survey_id))
    return {"items": items, "counts": counts}


@router.patch("/{request_id}", response_model=ContactRequest)
def update_contact_request(
    request_id: UUID, data: ContactRequestUpdate, db: TenantDB = Depends(tenant_db)
) -> dict:
    """Set the status as the team replies: new, contacted or done."""
    with db() as conn:
        if not repo.set_status(conn, request_id, data.status):
            raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
        row = repo.get(conn, request_id)
    return row


@router.post("/{request_id}/resolve", response_model=ContactRequest)
async def resolve_contact_request(
    request_id: UUID,
    data: ContactRequestResolve,
    user: CurrentUser = Depends(current_user),
    db: TenantDB = Depends(tenant_db),
    events: LianaEvents = Depends(get_liana_events),
) -> dict:
    """Mark the request as done and send the reader the team's "You said, we did"
    message through the Liana connector. A request is resolved once; only a
    message that failed to go out can be sent again (409 otherwise). If the
    message cannot be queued, `reply_status` becomes 'failed' and the call is 503."""

    def mark_resolved() -> dict:
        with db() as conn:
            exists, reply_status = repo.reply_status_for_update(conn, request_id)
            if not exists:
                raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
            try:
                domain.check_can_resolve(reply_status)
            except domain.AlreadyResolved as error:
                raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
            repo.resolve(conn, request_id, data.message)
            return repo.get(conn, request_id)

    row = await run_in_threadpool(mark_resolved)
    message = ContactResolved(
        tenant_id=user.tenant_id,
        survey_id=row["survey_id"],
        contact_request_id=request_id,
        contact_ref=row["contact_ref"],
        message=data.message,
    )
    try:
        await events.publish(message)
    except Exception as error:
        log.exception("could not queue the reply for contact request %s", request_id)

        def mark_failed() -> None:
            with db() as conn:
                repo.set_reply_status(conn, request_id, "failed")

        await run_in_threadpool(mark_failed)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, NOT_QUEUED) from error
    return row
