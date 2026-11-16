"""Survey manager endpoints: /api/v1/surveys."""

from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status

from ...auth.dev_stub import CurrentUser, current_user
from ...db import tenant_db
from . import repository
from .schemas import Survey, SurveyCreate, SurveyUpdate

router = APIRouter(prefix="/api/v1/surveys", tags=["surveys"])

NOT_FOUND = "Survey not found"


@router.post("", response_model=Survey, status_code=status.HTTP_201_CREATED)
def create_survey(
    data: SurveyCreate,
    user: CurrentUser = Depends(current_user),
    conn: psycopg.Connection = Depends(tenant_db),
) -> dict:
    """Create a survey. New surveys are always drafts."""
    return repository.create(conn, user.tenant_id, user.user_id, data)


@router.get("", response_model=list[Survey])
def list_surveys(conn: psycopg.Connection = Depends(tenant_db)) -> list[dict]:
    """All surveys of the current organisation, most recently changed first."""
    return repository.list_all(conn)


@router.get("/{survey_id}", response_model=Survey)
def get_survey(survey_id: UUID, conn: psycopg.Connection = Depends(tenant_db)) -> dict:
    row = repository.get(conn, survey_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return row


@router.patch("/{survey_id}", response_model=Survey)
def update_survey(
    survey_id: UUID, data: SurveyUpdate, conn: psycopg.Connection = Depends(tenant_db)
) -> dict:
    """Change the title or type. Fields left out stay the same."""
    row = repository.update(conn, survey_id, data)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return row
