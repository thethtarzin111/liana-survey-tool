"""Results rules: plain Python, no framework code."""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from liana_survey_shared.scoring import csat_score, headline, nps_score, thumbs_score


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


def compare_scores(survey_type: str, rows: list[dict]) -> dict:
    groups: dict[str, dict[str, dict[str, int]]] = {"segments": {}, "months": {}}
    for row in rows:
        for category, key in (("segments", row["segment"]), ("months", str(row["month"]))):
            counts = groups[category].setdefault(key, {})
            value = str(int(row["value_number"]))
            counts[value] = counts.get(value, 0) + row["count"]

    def score(counts):
        if survey_type == "nps":
            return nps_score(counts).score
        if survey_type == "thumbs":
            return thumbs_score(counts).positive
        if survey_type == "csat":
            return csat_score(counts).satisfied
        return None

    return {
        category: [
            {"label": key, "score": score(counts), "answers": sum(counts.values())}
            for key, counts in sorted(values.items())
        ]
        for category, values in groups.items()
    }
