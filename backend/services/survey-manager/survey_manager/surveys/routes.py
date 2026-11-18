"""Survey manager endpoints: /api/v1/surveys."""

import secrets
from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.concurrency import run_in_threadpool

from liana_survey_shared import links
from liana_survey_shared.config import get_settings
from liana_survey_shared.web.auth import CurrentUser, current_user
from liana_survey_shared.web.db import TenantDB, tenant_db

from . import branding, domain, repo
from .schemas import (
    Survey,
    SurveyCreate,
    SurveyListItem,
    SurveyStatus,
    SurveyUpdate,
    TestLinks,
    TestLinksRequest,
)

router = APIRouter(prefix="/api/v1/surveys", tags=["surveys"])

NOT_FOUND = "Survey not found"

# Each handler opens the transaction with `with db() as conn:` and returns
# inside it, so the commit happens before the response is sent.


@router.post("", response_model=Survey, status_code=status.HTTP_201_CREATED)
def create_survey(
    data: SurveyCreate,
    user: CurrentUser = Depends(current_user),
    db: TenantDB = Depends(tenant_db),
) -> dict:
    """Create a survey. New surveys are always drafts."""
    with db() as conn:
        return repo.create(conn, user.tenant_id, user.user_id, data)


@router.get("", response_model=list[SurveyListItem])
def list_surveys(
    q: Annotated[str | None, Query(max_length=200, description="Text in the title")] = None,
    survey_status: Annotated[SurveyStatus | None, Query(alias="status")] = None,
    db: TenantDB = Depends(tenant_db),
) -> list[dict]:
    """Surveys of the current organisation, most recently changed first.
    Filter by text in the title (`q`, any case) and by `status`."""
    search = q.strip() if q else None
    with db() as conn:
        return repo.list_all(conn, search or None, survey_status)


@router.get("/{survey_id}", response_model=Survey)
def get_survey(survey_id: UUID, db: TenantDB = Depends(tenant_db)) -> dict:
    with db() as conn:
        row = repo.get(conn, survey_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return row


@router.patch("/{survey_id}", response_model=Survey)
def update_survey(survey_id: UUID, data: SurveyUpdate, db: TenantDB = Depends(tenant_db)) -> dict:
    """Change the title, description or type. Fields left out stay the same."""
    with db() as conn:
        row = repo.update(conn, survey_id, data)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return row


@router.post("/{survey_id}/duplicate", response_model=Survey, status_code=status.HTTP_201_CREATED)
def duplicate_survey(
    survey_id: UUID,
    user: CurrentUser = Depends(current_user),
    db: TenantDB = Depends(tenant_db),
) -> dict:
    """Copy a survey and its questions into a new draft called "<title> (copy)".
    Dates, responses and results are not copied."""
    with db() as conn:
        original = repo.get(conn, survey_id)
        if original is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
        title = domain.copy_title(original["title"])
        return repo.duplicate(conn, user.tenant_id, user.user_id, survey_id, title)


@router.post("/{survey_id}/publish", response_model=Survey)
def publish_survey(survey_id: UUID, db: TenantDB = Depends(tenant_db)) -> dict:
    """Make a draft live and give it its public link. Other statuses, and drafts
    missing their questions, get 409."""
    with db() as conn:
        row = repo.get_for_update(conn, survey_id)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
        try:
            domain.published_status(
                SurveyStatus(row["status"]), row["type"], repo.question_texts(conn, survey_id)
            )
        except (domain.StatusChangeNotAllowed, domain.NotReadyToPublish) as error:
            raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
        return repo.publish(conn, survey_id, domain.new_link_token())


@router.post("/{survey_id}/test-links", response_model=TestLinks)
def make_test_links(
    survey_id: UUID,
    data: TestLinksRequest | None = None,
    db: TenantDB = Depends(tenant_db),
) -> dict:
    """Answer links for made-up readers, to try a live survey before the
    LianaMailer snippet (#40) exists. Local development (AUTH_MODE=dev) only."""
    settings = get_settings()
    if settings.auth_mode != "dev":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    with db() as conn:
        row = repo.get(conn, survey_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    if row["status"] != SurveyStatus.live.value or not row["link_token"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "Publish the survey first.")
    count = (data or TestLinksRequest()).count
    batch = secrets.token_hex(3)
    return {
        "links": [
            links.answer_link(
                settings.public_base_url,
                settings.link_signing_secret,
                row["link_token"],
                f"test-{batch}-{n}",
            )
            for n in range(1, count + 1)
        ]
    }


@router.post("/{survey_id}/close", response_model=Survey)
def close_survey(survey_id: UUID, db: TenantDB = Depends(tenant_db)) -> dict:
    """Stop a live survey from taking answers. Other statuses get 409."""
    return _change_status(db, survey_id, domain.closed_status)


@router.post("/{survey_id}/unpublish", response_model=Survey)
def unpublish_survey(survey_id: UUID, db: TenantDB = Depends(tenant_db)) -> dict:
    """Turn a live or scheduled survey back into a draft. Other statuses get 409."""
    return _change_status(db, survey_id, domain.unpublished_status)


@router.delete("/{survey_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_survey(survey_id: UUID, db: TenantDB = Depends(tenant_db)) -> Response:
    """Delete a survey with its questions, responses and answers. This cannot be undone."""
    with db() as conn:
        deleted = repo.delete(conn, survey_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _change_status(
    db: TenantDB, survey_id: UUID, rule: Callable[[SurveyStatus], SurveyStatus]
) -> dict:
    with db() as conn:
        row = repo.get_for_update(conn, survey_id)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
        try:
            new_status = rule(SurveyStatus(row["status"]))
        except domain.StatusChangeNotAllowed as error:
            raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
        return repo.set_status(conn, survey_id, new_status)


# --- Logo (#66) ----------------------------------------------------------------

#: Served with the logo so that, even opened on its own, an SVG cannot run code.
LOGO_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "private, max-age=86400",
}


@router.put(
    "/{survey_id}/logo",
    response_model=Survey,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                kind: {"schema": {"type": "string", "format": "binary"}}
                for kind in branding.LOGO_TYPES
            },
        }
    },
)
async def upload_logo(
    survey_id: UUID,
    request: Request,
    user: CurrentUser = Depends(current_user),
    db: TenantDB = Depends(tenant_db),
) -> dict:
    """Upload or replace the logo: send the image itself as the body, with its
    Content-Type. PNG, JPG, SVG or WebP, at most 1 MB."""
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > branding.MAX_LOGO_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "the logo can be at most 1 MB")
    # Read at most one byte more than allowed, so a large upload sent without a
    # Content-Length (chunked) is never held in memory in full.
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > branding.MAX_LOGO_BYTES:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "the logo can be at most 1 MB")
        chunks.append(chunk)
    data = b"".join(chunks)
    try:
        kind = branding.check_logo(request.headers.get("content-type", ""), data)
    except branding.LogoTooLarge as error:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, str(error)) from error
    except branding.LogoError as error:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(error)) from error

    def save() -> dict | None:
        with db() as conn:
            return repo.put_logo(conn, user.tenant_id, survey_id, kind, data)

    row = await run_in_threadpool(save)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return row


@router.get(
    "/{survey_id}/logo",
    response_class=Response,
    responses={200: {"content": {kind: {} for kind in branding.LOGO_TYPES}}, 404: {}},
)
def get_logo(survey_id: UUID, db: TenantDB = Depends(tenant_db)) -> Response:
    """The survey's logo image."""
    with db() as conn:
        logo = repo.get_logo(conn, survey_id)
    if logo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No logo for this survey")
    return Response(bytes(logo["data"]), media_type=logo["content_type"], headers=LOGO_HEADERS)


@router.delete("/{survey_id}/logo", status_code=status.HTTP_204_NO_CONTENT)
def delete_logo(survey_id: UUID, db: TenantDB = Depends(tenant_db)) -> Response:
    """Remove the logo. Surveys without a logo also get 204."""
    with db() as conn:
        found = repo.delete_logo(conn, survey_id)
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
