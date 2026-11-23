"""Template endpoints: /api/v1/templates."""

from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from liana_survey_shared.web.auth import CurrentUser, current_user
from liana_survey_shared.web.db import TenantDB, tenant_db

from ..questions import repo as question_repo
from ..surveys import repo as survey_repo
from ..surveys.schemas import Survey, SurveyType
from . import domain, repo
from .schemas import Template, TemplateCreate, TemplateUpdate

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])

NOT_FOUND = "Template not found"
SURVEY_NOT_FOUND = "Survey not found"


@router.get("", response_model=list[Template])
def list_templates(
    survey_type: Annotated[SurveyType | None, Query(alias="type")] = None,
    user: CurrentUser = Depends(current_user),
    db: TenantDB = Depends(tenant_db),
) -> list[dict]:
    """Built-in templates and the organisation's own, in display order.
    Filter by survey `type`, as on "Pick a template"."""
    with db() as conn:
        rows = repo.list_all(conn, survey_type)
    return [domain.template_for(row, user.tenant_name) for row in rows]


@router.post("", response_model=Template, status_code=status.HTTP_201_CREATED)
def save_as_template(
    data: TemplateCreate,
    user: CurrentUser = Depends(current_user),
    db: TenantDB = Depends(tenant_db),
) -> dict:
    """Save a survey as the organisation's own template: its type, questions,
    thank-you message and branding colours, under a new name and description."""
    with db() as conn:
        survey = survey_repo.get(conn, data.survey_id)
        if survey is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, SURVEY_NOT_FOUND)
        try:
            questions = domain.saved_questions(question_repo.list_all(conn, data.survey_id))
        except domain.NoQuestions as error:
            raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
        row = repo.create(conn, user.tenant_id, data.name, data.description, survey, questions)
    return domain.template_for(row, user.tenant_name)


@router.patch("/{template_id}", response_model=Template)
def update_template(
    template_id: UUID,
    data: TemplateUpdate,
    user: CurrentUser = Depends(current_user),
    db: TenantDB = Depends(tenant_db),
) -> dict:
    """Rename one of the organisation's own templates or change its description.
    Built-in templates get 403."""
    with db() as conn:
        _own_template(conn, template_id)
        row = repo.update(conn, template_id, data)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return domain.template_for(row, user.tenant_name)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(template_id: UUID, db: TenantDB = Depends(tenant_db)) -> Response:
    """Delete one of the organisation's own templates. Surveys made from it stay.
    Built-in templates get 403."""
    with db() as conn:
        _own_template(conn, template_id)
        deleted = repo.delete(conn, template_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _own_template(conn: psycopg.Connection, template_id: UUID) -> None:
    """404 for templates the organisation cannot see, 403 for built-in ones."""
    template = repo.get(conn, template_id)
    if template is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    try:
        domain.check_own(template)
    except domain.BuiltInTemplate as error:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(error)) from error


@router.post("/{template_id}/surveys", response_model=Survey, status_code=status.HTTP_201_CREATED)
def create_survey_from_template(
    template_id: UUID,
    user: CurrentUser = Depends(current_user),
    db: TenantDB = Depends(tenant_db),
) -> dict:
    """Create a draft survey from a template: its name, type, thank-you message, questions
    and, for the organisation's own templates, branding colours."""
    with db() as conn:
        template = repo.get(conn, template_id)
        if template is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
        questions = domain.survey_questions(template, user.tenant_name)
        colours = domain.survey_colours(template)
        return repo.create_survey(conn, user.tenant_id, user.user_id, template, questions, colours)
