"""Question endpoints nested under /api/v1/surveys/{survey_id}."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from liana_survey_shared.web.auth import CurrentUser, current_user
from liana_survey_shared.web.db import TenantDB, tenant_db

from . import repo
from .schemas import Question, QuestionCreate, QuestionOrder, QuestionUpdate

router = APIRouter(prefix="/api/v1/surveys/{survey_id}/questions", tags=["questions"])

SURVEY_NOT_FOUND = "Survey not found"
QUESTION_NOT_FOUND = "Question not found"


def require_survey(conn, survey_id: UUID) -> None:
    if not repo.lock_survey(conn, survey_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, SURVEY_NOT_FOUND)


@router.get("", response_model=list[Question])
def list_questions(survey_id: UUID, db: TenantDB = Depends(tenant_db)) -> list[dict]:
    with db() as conn:
        require_survey(conn, survey_id)
        return repo.list_all(conn, survey_id)


@router.post("", response_model=Question, status_code=status.HTTP_201_CREATED)
def add_question(
    survey_id: UUID,
    data: QuestionCreate,
    user: CurrentUser = Depends(current_user),
    db: TenantDB = Depends(tenant_db),
) -> dict:
    with db() as conn:
        require_survey(conn, survey_id)
        row = repo.create(conn, user.tenant_id, survey_id, data)
        assert row is not None
        return row


@router.put("/order", response_model=list[Question])
def reorder_questions(
    survey_id: UUID, data: QuestionOrder, db: TenantDB = Depends(tenant_db)
) -> list[dict]:
    with db() as conn:
        require_survey(conn, survey_id)
        if not repo.reorder(conn, survey_id, data.question_ids):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "question_ids must contain every question in this survey exactly once",
            )
        return repo.list_all(conn, survey_id)


@router.patch("/{question_id}", response_model=Question)
def edit_question(
    survey_id: UUID,
    question_id: UUID,
    data: QuestionUpdate,
    db: TenantDB = Depends(tenant_db),
) -> dict:
    with db() as conn:
        require_survey(conn, survey_id)
        row = repo.update(conn, survey_id, question_id, data)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, QUESTION_NOT_FOUND)
        return row


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(
    survey_id: UUID, question_id: UUID, db: TenantDB = Depends(tenant_db)
) -> Response:
    with db() as conn:
        require_survey(conn, survey_id)
        if not repo.delete(conn, survey_id, question_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, QUESTION_NOT_FOUND)
        return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{question_id}/duplicate", response_model=Question, status_code=status.HTTP_201_CREATED
)
def duplicate_question(
    survey_id: UUID,
    question_id: UUID,
    user: CurrentUser = Depends(current_user),
    db: TenantDB = Depends(tenant_db),
) -> dict:
    with db() as conn:
        require_survey(conn, survey_id)
        row = repo.duplicate(conn, user.tenant_id, survey_id, question_id)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, QUESTION_NOT_FOUND)
        return row
