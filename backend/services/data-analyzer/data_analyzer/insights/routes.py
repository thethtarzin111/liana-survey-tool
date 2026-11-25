from functools import lru_cache
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from liana_survey_shared.config import get_settings
from liana_survey_shared.web.db import TenantDB, tenant_db

from ..routes import SegmentQuery, resolve_segment
from . import domain, repo
from .adapters import build_grouper, build_writer
from .ports import CommentGrouper, ThemeWriter
from .schemas import CommentInsights

router = APIRouter(prefix="/api/v1/results", tags=["results"])


@lru_cache
def grouper() -> CommentGrouper:
    """One grouper per process, so a model is loaded once."""
    return build_grouper(get_settings())


@lru_cache
def writer() -> ThemeWriter:
    return build_writer(get_settings())


@router.get("/{survey_id}/comment-insights", response_model=CommentInsights)
def comment_insights(
    survey_id: UUID,
    segment: SegmentQuery = "all",
    db: TenantDB = Depends(tenant_db),
    group_with: CommentGrouper = Depends(grouper),
    write_with: ThemeWriter = Depends(writer),
) -> dict:
    """Themes in the survey's comments. Theme names, summaries and quote picks come from
    the theme writer (an LLM, or the mock); every count, percentage and score is computed
    in code, and quotes are kept only when found word-for-word. Comments are redacted
    before anything reads them."""
    with db() as conn:
        stored = resolve_segment(conn, survey_id, segment)
        data = repo.comment_rows(conn, survey_id, stored)
    if data is None:
        raise HTTPException(404, "Survey not found")
    comments, redacted = domain.collect(data["rows"])
    result = domain.analyse(comments, data["kind"], data["reasons"], group_with, write_with)
    return {
        **result,
        "survey_id": survey_id,
        "kind": data["kind"],
        "comments": len(comments),
        "redacted": redacted,
        "min_comments": domain.MIN_COMMENTS,
        "direct_limit": domain.DIRECT_LIMIT,
    }
