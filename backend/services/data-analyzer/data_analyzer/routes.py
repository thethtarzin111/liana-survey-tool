from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from liana_survey_shared.scoring import CSAT_SCALE, NPS_SCALE, THUMBS_SCALE, answer_split, headline
from liana_survey_shared.web.db import TenantDB, tenant_db

from . import repo
from .schemas import SurveyResult

router = APIRouter(prefix="/api/v1/results", tags=["results"])
Segment = Annotated[str, Query(pattern=r"^(?:all|[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?)$")]
SCALES = {"thumbs": THUMBS_SCALE, "nps": NPS_SCALE, "csat": CSAT_SCALE}


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
        "comments": row["comments"],
        "headline": {"score": score.score, "note": score.note} if score else None,
        "split": [share.__dict__ for share in answer_split(row["distribution"], scale)],
    }
