"""Survey performance rules: plain Python, no framework code."""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from zoneinfo import ZoneInfo

from liana_survey_shared.scoring import Counts, csat_score, headline, nps_score, thumbs_score

# A segment with fewer answers is never shown on its own (anonymity).
MIN_GROUP = 5
TIME_ZONE = ZoneInfo("Europe/Helsinki")


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


@dataclass(frozen=True)
class SegmentGroup:
    """One segment as shown: its filter value, label, answers and stored values."""

    value: str
    label: str
    answers: int
    members: tuple[str, ...]


def segment_label(stored: str) -> str:
    """The label of a stored segment: "all" is "No segment", else capitalised."""
    return "No segment" if stored == "all" else stored.capitalize()


def segment_groups(counts: dict[str, int]) -> list[SegmentGroup]:
    """Segments with enough answers, most first. Small ones are grouped into Other.

    Other comes last and is left out when it has fewer than MIN_GROUP answers.
    """
    shown = [
        SegmentGroup("none" if stored == "all" else stored, segment_label(stored), n, (stored,))
        for stored, n in counts.items()
        if n >= MIN_GROUP
    ]
    shown.sort(key=lambda g: (-g.answers, g.value))
    small = sorted((stored, n) for stored, n in counts.items() if n < MIN_GROUP)
    total = sum(n for _, n in small)
    if total >= MIN_GROUP:
        shown.append(SegmentGroup("other", "Other", total, tuple(s for s, _ in small)))
    return shown


def stored_segments(groups: list[SegmentGroup], value: str) -> tuple[str, ...] | None:
    """The stored values a filter value stands for, None for an unknown or small segment."""
    for group in groups:
        if group.value == value:
            return group.members
    return None


def score(kind: str, counts: Counts) -> int | None:
    """The main score of a question kind: NPS, thumbs positive % or rating satisfied %."""
    if kind == "nps":
        return nps_score(counts).score
    if kind == "thumbs":
        return thumbs_score(counts).positive
    if kind == "rating":
        return csat_score(counts).satisfied
    return None


def month_of(ts: datetime) -> str:
    """The calendar month of a moment in Helsinki time, like "2026-11"."""
    return ts.astimezone(TIME_ZONE).strftime("%Y-%m")
