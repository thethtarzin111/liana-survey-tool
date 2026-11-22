from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class PerformanceRow(BaseModel):
    survey_id: UUID
    survey: str
    channel: Literal["email", "link", "qr"]
    views: int
    responses: int
    response_rate: int | None
    main_result: str | None


class OverviewSegment(BaseModel):
    value: str
    label: str
    answers: int


class OverviewMain(BaseModel):
    question_id: UUID
    kind: Literal["nps", "thumbs", "rating"]
    score: int | None
    change: int | None
    counts: dict[str, int]


class OverviewOption(BaseModel):
    label: str
    count: int


class OverviewQuestion(BaseModel):
    id: UUID
    kind: str
    prompt: str
    required: bool
    answers: int
    options: list[OverviewOption]
    average: float | None


class OverviewReason(BaseModel):
    label: str
    count: int
    percent: int | None


class OverviewMonth(BaseModel):
    month: str
    score: int | None
    answers: int


class OverviewSegmentScore(BaseModel):
    value: str
    label: str
    answers: int
    score: int | None
    counts: dict[str, int]


class SurveyOverview(BaseModel):
    survey_id: UUID
    title: str
    type: Literal["thumbs", "nps", "csat", "custom"]
    status: Literal["draft", "scheduled", "live", "closed"]
    closes_at: datetime | None
    last_answer_at: datetime | None
    channels: list[Literal["email", "link", "qr"]]
    segment: str
    segments: list[OverviewSegment]
    responses: int
    views: int
    response_rate: int | None
    completed_all: int | None
    main: OverviewMain | None
    questions: list[OverviewQuestion]
    reasons: list[OverviewReason]
    trend: list[OverviewMonth]
    by_segment: list[OverviewSegmentScore]


class ResponseRow(BaseModel):
    id: UUID
    display_id: str
    submitted_at: datetime
    answer: int | None
    reason: str | None
    comment: str | None
    masked: bool
    segment_label: str | None


class ResponsesPage(BaseModel):
    total: int
    rows: list[ResponseRow]


class ResponseAnswer(BaseModel):
    question_id: UUID
    prompt: str
    kind: str
    value: int | float | str | list[str] | None
    masked: bool


class ResponseDetail(BaseModel):
    display_id: str
    submitted_at: datetime
    segment_label: str | None
    answers: list[ResponseAnswer]
