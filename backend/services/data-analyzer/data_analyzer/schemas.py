from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class Headline(BaseModel):
    score: str
    note: str


class AnswerShare(BaseModel):
    value: int
    count: int
    percent: int | None


class SurveyResult(BaseModel):
    survey_id: UUID
    title: str
    type: Literal["thumbs", "nps", "csat", "custom"]
    status: Literal["draft", "scheduled", "live", "closed"]
    answers: int
    segment: str
    segments: list[str]
    headline: Headline | None
    split: list[AnswerShare]
    questions: list[dict] = []


class PerformanceRow(BaseModel):
    survey_id: UUID
    survey: str
    channel: Literal["email", "link", "qr"]
    views: int
    responses: int
    response_rate: int | None
    main_result: str | None
