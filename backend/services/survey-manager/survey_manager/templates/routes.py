"""Template endpoints: /api/v1/templates."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from liana_survey_shared.web.auth import CurrentUser, current_user
from liana_survey_shared.web.db import TenantDB, tenant_db

from ..surveys.schemas import Survey, SurveyType
from . import domain, repo
from .schemas import Template

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])

NOT_FOUND = "Template not found"


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


@router.post("/{template_id}/surveys", response_model=Survey, status_code=status.HTTP_201_CREATED)
def create_survey_from_template(
    template_id: UUID,
    user: CurrentUser = Depends(current_user),
    db: TenantDB = Depends(tenant_db),
) -> dict:
    """Create a draft survey from a template: its name, type, thank-you message and questions."""
    with db() as conn:
        template = repo.get(conn, template_id)
        if template is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
        questions = domain.survey_questions(template, user.tenant_name)
        return repo.create_survey(conn, user.tenant_id, user.user_id, template, questions)
