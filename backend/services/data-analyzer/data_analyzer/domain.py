"""Survey performance rules: plain Python, no framework code."""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from liana_survey_shared.scoring import headline


def response_rate(responses: int, views: int) -> int | None:
    """Responses as a whole percentage of views, or None when nothing was viewed."""
    if views <= 0:
        return None
    return int((Decimal(responses) * 100 / Decimal(views)).quantize(Decimal(1), ROUND_HALF_UP))


def performance_row(row: dict[str, Any]) -> dict[str, Any]:
    """One survey and channel as the API shows it: its rate and its own main result."""
    score = headline(row["type"], row["distribution"])
    return {
        **row,
        "response_rate": response_rate(row["responses"], row["views"]),
        "main_result": score.score if score else None,
    }
