"""Survey manager endpoints: /api/v1/surveys."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from liana_survey_shared.web.auth import CurrentUser, current_user
from liana_survey_shared.web.db import TenantDB, tenant_db

from . import repo
from .schemas import Survey, SurveyCreate, SurveyUpdate

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


@router.get("", response_model=list[Survey])
def list_surveys(db: TenantDB = Depends(tenant_db)) -> list[dict]:
    """All surveys of the current organisation, most recently changed first."""
    with db() as conn:
        return repo.list_all(conn)


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
