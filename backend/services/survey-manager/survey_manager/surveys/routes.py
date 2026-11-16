"""Survey manager endpoints: /api/v1/surveys."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from liana_survey_shared.web.auth import CurrentUser, current_user
from liana_survey_shared.web.db import TenantDB, tenant_db

from . import domain, repo
from .schemas import Survey, SurveyCreate, SurveyListItem, SurveyStatus, SurveyUpdate

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
