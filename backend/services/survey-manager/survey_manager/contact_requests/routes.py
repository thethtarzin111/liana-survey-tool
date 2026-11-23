"""Contact request endpoints: /api/v1/contact-requests."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from liana_survey_shared.web.db import TenantDB, tenant_db

from . import domain, repo
from .domain import Status
from .schemas import ContactRequest, ContactRequestList, ContactRequestUpdate

router = APIRouter(prefix="/api/v1/contact-requests", tags=["contact requests"])

NOT_FOUND = "Contact request not found"


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
