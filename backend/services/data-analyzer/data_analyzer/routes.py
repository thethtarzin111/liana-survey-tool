from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from liana_survey_shared.scoring import CSAT_SCALE, NPS_SCALE, THUMBS_SCALE, answer_split, headline
from liana_survey_shared.web.db import TenantDB, tenant_db

from . import domain, repo
from .schemas import PerformanceRow, SurveyResult

router = APIRouter(prefix="/api/v1/results", tags=["results"])
Segment = Annotated[str, Query(pattern=r"^(?:all|[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?)$")]
SCALES = {"thumbs": THUMBS_SCALE, "nps": NPS_SCALE, "csat": CSAT_SCALE}


@router.get("/responses")
def response_feed(
    survey_id: UUID | None = None,
    segment: Segment = "all",
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: TenantDB = Depends(tenant_db),
) -> list[dict]:
    """Responses in stable newest-first order, filtered before pagination."""
    with db() as conn:
        return repo.response_feed(conn, survey_id, segment, limit, offset)


@router.get("/performance", response_model=list[PerformanceRow])
def survey_performance(
    limit: Annotated[
        int | None, Query(ge=1, le=100, description="Surveys to include; all when left out")
    ] = None,
    offset: Annotated[int, Query(ge=0, description="Surveys to skip")] = 0,
    db: TenantDB = Depends(tenant_db),
) -> list[dict]:
    """Views, responses and response rate for every used survey channel. Surveys with
    the latest views or answers come first; `limit` counts surveys, not rows."""
    with db() as conn:
        rows = repo.performance_rows(conn, limit=limit, offset=offset)
    return [domain.performance_row(row) for row in rows]


# After /responses and /performance, so those paths are not read as survey ids.
@router.get("/{survey_id}", response_model=SurveyResult)
def get_result(
    survey_id: UUID, segment: Segment = "all", db: TenantDB = Depends(tenant_db)
) -> dict:
    with db() as conn:
        row = repo.survey_result(conn, survey_id, segment)
        comparison = (
            domain.compare_scores(row["type"], repo.score_groups(conn, survey_id, segment))
            if row
            else {}
        )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Survey not found")
    score = headline(row["type"], row["distribution"])
    scale = SCALES.get(row["type"], ())
    return {
        "survey_id": row["id"],
        "title": row["title"],
        "type": row["type"],
        "status": row["status"],
        "answers": row["answers"],
        "segment": segment,
        "segments": row["segments"],
        "questions": row["questions"],
        "comments": row["comments"],
        "comparison": comparison,
        "headline": {"score": score.score, "note": score.note} if score else None,
        "split": [share.__dict__ for share in answer_split(row["distribution"], scale)],
    }


@router.get("/{survey_id}/reasons")
def get_reasons(
    survey_id: UUID, segment: Segment = "all", db: TenantDB = Depends(tenant_db)
) -> list[dict]:
    """Reason questions and ranked option counts for the selected segment."""
    with db() as conn:
        _require_survey(conn, survey_id)
        questions = repo.question_charts(conn, survey_id, segment)
    return [
        {
            **question,
            "options": sorted(
                question["options"], key=lambda option: (-option["count"], option["label"])
            ),
        }
        for question in questions
        if question["kind"] == "reasons"
    ]


@router.get("/{survey_id}/comments")
def get_comments(
    survey_id: UUID, segment: Segment = "all", db: TenantDB = Depends(tenant_db)
) -> list[dict]:
    """Latest 100 nonblank comments with answer, segment and submission time."""
    with db() as conn:
        _require_survey(conn, survey_id)
        return repo.comments(conn, survey_id, segment)


def _require_survey(conn, survey_id: UUID) -> None:
    if conn.execute("select id from surveys where id = %s", (survey_id,)).fetchone() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Survey not found")
