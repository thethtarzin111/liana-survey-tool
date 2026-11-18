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
