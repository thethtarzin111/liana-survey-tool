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


# After /performance, so that path is not read as a survey id.
@router.get("/{survey_id}", response_model=SurveyResult)
def get_result(
    survey_id: UUID, segment: Segment = "all", db: TenantDB = Depends(tenant_db)
) -> dict:
    with db() as conn:
        row = repo.survey_result(conn, survey_id, segment)
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
        "headline": {"score": score.score, "note": score.note} if score else None,
        "split": [share.__dict__ for share in answer_split(row["distribution"], scale)],
    }
