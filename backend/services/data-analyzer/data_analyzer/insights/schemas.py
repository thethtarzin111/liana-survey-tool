from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class InsightQuote(BaseModel):
    comment_id: str
    #: Found word-for-word in the (redacted) comment.
    text: str
    summary: str


class InsightSentiment(BaseModel):
    negative: int
    neutral: int
    positive: int


class InsightTheme(BaseModel):
    key: str
    label: str
    outlier: bool
    comments: int
    percent: int | None
    sentiment: InsightSentiment
    score: int | None
    score_vs_all: int | None
    quotes: list[InsightQuote]
    hidden_quotes: int
    samples: list[str]


class NegativeTheme(BaseModel):
    key: str
    label: str
    count: int
    percent: int | None


class InsightRun(BaseModel):
    grouper: str | None
    writer: str
    llm_calls: int


class CommentInsights(BaseModel):
    survey_id: UUID
    status: Literal["ready", "too_few"]
    mode: Literal["direct", "clustered"] | None
    kind: Literal["nps", "thumbs", "rating"] | None
    comments: int
    redacted: int
    min_comments: int
    direct_limit: int
    score: int | None = None
    themes: list[InsightTheme]
    negative_themes: list[NegativeTheme]
    run: InsightRun
