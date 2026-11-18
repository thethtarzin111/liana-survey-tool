"""Survey performance rules: plain Python, no framework code."""

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from liana_survey_shared.scoring import (
    CSAT_SCALE,
    NPS_SCALE,
    THUMBS_SCALE,
    Counts,
    csat_score,
    headline,
    nps_score,
    thumbs_score,
    top_reasons,
)

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
    main = headline(row["type"], row["distribution"])
    return {
        **row,
        "response_rate": response_rate(row["responses"], row["views"]),
        "main_result": main.score if main else None,
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


def segments_enabled(groups: list[SegmentGroup], total: int) -> bool:
    """Segments may be shown or filtered only when 2 or more groups cover every response.

    Otherwise a reader could subtract the shown groups from the total and learn the
    size and answers of a hidden small segment."""
    return len(groups) >= 2 and sum(g.answers for g in groups) == total


def available_groups(counts: dict[str, int]) -> list[SegmentGroup]:
    """The groups readers may see and filter by: empty when segments are not enabled."""
    groups = segment_groups(counts)
    return groups if segments_enabled(groups, sum(counts.values())) else []


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


SCALES = {"nps": NPS_SCALE, "thumbs": THUMBS_SCALE, "rating": CSAT_SCALE}
CHOICE_KINDS = ("single_choice", "multiple_choice", "dropdown", "reasons")


def _average(counts: dict[str, int]) -> float | None:
    """Mean answer on one decimal, or None without answers."""
    total = sum(counts.values())
    if not total:
        return None
    weighted = sum(int(value) * n for value, n in counts.items())
    return float((Decimal(weighted) / Decimal(total)).quantize(Decimal("0.1"), ROUND_HALF_UP))


def _question(question: dict[str, Any], answers: int, counts: dict[str, int]) -> dict[str, Any]:
    """One question with its answer count and the options in their visual order."""
    kind = question["kind"]
    if kind in SCALES:
        labels = [str(value) for value in SCALES[kind]]
    elif kind in CHOICE_KINDS:
        labels = list(question["options"])
        labels += [label for label in counts if label not in labels]
    else:
        labels = []
    return {
        "id": question["id"],
        "kind": kind,
        "prompt": question["prompt"],
        "required": question["required"],
        "answers": answers,
        "options": [{"label": label, "count": counts.get(label, 0)} for label in labels],
        "average": _average(counts) if kind in SCALES else None,
    }


def _sum_counts(rows: list[dict[str, Any]], scale: tuple[int, ...]) -> dict[str, int]:
    """Answer counts per scale value, every value present."""
    counts = {str(value): 0 for value in scale}
    for row in rows:
        if row["value"] in counts:
            counts[row["value"]] += row["n"]
    return counts


def overview(rows: dict[str, Any], segment: str) -> dict[str, Any]:
    """The survey overview from `repo.overview_rows`: KPIs, a summary per question,
    the main score by month and by segment. `segment` is the chosen filter value."""
    survey = rows["survey"]
    segment_counts = rows["segment_counts"]
    groups = available_groups(segment_counts)
    chosen = None if segment == "all" else stored_segments(groups, segment)
    responses = sum(n for stored, n in segment_counts.items() if chosen is None or stored in chosen)
    views = rows["views"]
    questions = rows["questions"]

    summaries = [
        _question(q, rows["answered"].get(q["id"], 0), rows["values"].get(q["id"], {}))
        for q in questions
    ]

    main = next((q for q in questions if q["kind"] in SCALES), None)
    main_info = None
    trend: list[dict[str, Any]] = []
    by_segment: list[dict[str, Any]] = []
    if main:
        scale = SCALES[main["kind"]]
        kept = [r for r in rows["main_rows"] if chosen is None or r["segment"] in chosen]
        counts = _sum_counts(kept, scale)
        this_month = month_of(rows["now"])
        before = _sum_counts([r for r in kept if r["month"] < this_month], scale)
        change = None
        if sum(before.values()):
            change = (score(main["kind"], counts) or 0) - (score(main["kind"], before) or 0)
        main_info = {
            "question_id": main["id"],
            "kind": main["kind"],
            "score": score(main["kind"], counts),
            "change": change,
            "counts": counts,
        }
        months = sorted({r["month"] for r in kept})
        if len(months) >= 2:
            for month in months:
                in_month = _sum_counts([r for r in kept if r["month"] == month], scale)
                trend.append(
                    {
                        "month": month,
                        "score": score(main["kind"], in_month),
                        "answers": sum(in_month.values()),
                    }
                )
        if groups:
            for group in groups:
                own = _sum_counts(
                    [r for r in rows["main_rows"] if r["segment"] in group.members], scale
                )
                by_segment.append(
                    {
                        "value": group.value,
                        "label": group.label,
                        "answers": group.answers,
                        "score": score(main["kind"], own),
                        "counts": own,
                    }
                )

    reasons: list[dict[str, Any]] = []
    first_reasons = next((s for s in summaries if s["kind"] == "reasons"), None)
    if first_reasons:
        picked = {o["label"]: o["count"] for o in first_reasons["options"]}
        reasons = [
            {"label": r.value, "count": r.count, "percent": r.percent}
            for r in top_reasons(picked, first_reasons["answers"])
        ]

    completed_all = None
    if survey["type"] == "custom" and questions:
        completed_all = response_rate(rows["completed"], responses)

    return {
        "survey_id": survey["id"],
        "title": survey["title"],
        "type": survey["type"],
        "status": survey["status"],
        "closes_at": survey["closes_at"],
        "last_answer_at": survey["last_answer_at"],
        "channels": rows["channels"],
        "segment": segment,
        "segments": (
            [{"value": g.value, "label": g.label, "answers": g.answers} for g in groups]
            if groups
            else []
        ),
        "responses": responses,
        "views": views,
        "response_rate": None if segment != "all" else response_rate(responses, views),
        "completed_all": completed_all,
        "main": main_info,
        "questions": summaries,
        "reasons": reasons,
        "trend": trend,
        "by_segment": by_segment,
    }


# Answer groups of the scale kinds, as values of the main question.
GROUPS: dict[str, dict[str, tuple[int, ...]]] = {
    "thumbs": {"not-for-me": (0,), "good": (1,), "loved-it": (2,)},
    "nps": {
        "detractors": tuple(range(0, 7)),
        "passives": (7, 8),
        "promoters": (9, 10),
    },
    "rating": {"low": (1, 2), "neutral": (3,), "high": (4, 5)},
}


def group_values(kind: str | None, group: str) -> tuple[int, ...] | None:
    """The answers an answer group stands for, None when the kind has no such group."""
    return GROUPS.get(kind or "", {}).get(group)


def segment_labels(groups: list[SegmentGroup]) -> dict[str, str]:
    """The label of every stored segment the shown groups cover."""
    return {stored: group.label for group in groups for stored in group.members}


# Patterns written for both PostgreSQL (regexp_replace with the "g" flag) and Python
# `re`: no lookarounds, no \b. A phone number starts with "+", "0" or "(0" and has
# at least 8 digits, spaces, brackets or dashes in all, so dates and plain numbers stay. The
# first group of PHONE_PATTERN is the character before the number and is kept.
EMAIL_PATTERN = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
PHONE_PATTERN = r"(^|[^0-9A-Za-z(])((\+[0-9]|\(?0)[0-9 ()-]{6,}[0-9])"
HIDDEN = "[hidden]"
EMAIL_REPLACEMENT = HIDDEN
PHONE_REPLACEMENT = r"\1" + HIDDEN

_EMAIL = re.compile(EMAIL_PATTERN)
_PHONE = re.compile(PHONE_PATTERN)


def mask(text: str) -> tuple[str, bool]:
    """The text with emails and phone numbers replaced, and whether anything was."""
    masked = _PHONE.sub(PHONE_REPLACEMENT, _EMAIL.sub(EMAIL_REPLACEMENT, text))
    return masked, masked != text


def display_id(response_id: UUID) -> str:
    """A short id for a response: "R-" and 6 hex characters of its hashed id."""
    digest = hashlib.sha256(str(response_id).encode()).hexdigest()
    return "R-" + digest[:6].upper()


def response_row(row: dict[str, Any], labels: dict[str, str]) -> dict[str, Any]:
    """One response of the list as the API shows it. The segment label is None when
    segments are off (`labels` is empty)."""
    return {
        "id": row["id"],
        "display_id": display_id(row["id"]),
        "submitted_at": row["submitted_at"],
        "answer": row["answer"],
        "reason": row["reason"],
        "comment": row["comment"],
        "masked": row["was_masked"],
        "segment_label": labels.get(row["segment"]),
    }


def _number(value: Any) -> int | float:
    return int(value) if value == int(value) else float(value)


def response_detail(detail: dict[str, Any], labels: dict[str, str]) -> dict[str, Any]:
    """One response with all its answers. Text is masked already, `masked` says whether
    a replacement was made."""
    answers = []
    for row in detail["answers"]:
        if row["value_number"] is not None:
            value: Any = _number(row["value_number"])
        elif row["value_choices"] is not None:
            value = row["value_choices"]
        else:
            value = row["text"]
        answers.append(
            {
                "question_id": row["question_id"],
                "prompt": row["prompt"],
                "kind": row["kind"],
                "value": value,
                "masked": row["raw_text"] is not None and row["text"] != row["raw_text"],
            }
        )
    return {
        "display_id": display_id(detail["id"]),
        "submitted_at": detail["submitted_at"],
        "segment_label": labels.get(detail["segment"]),
        "answers": answers,
    }


def _csv_text(text: str) -> str:
    """Text a spreadsheet would not run as a formula."""
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def csv_cell(answer: dict[str, Any] | None) -> str:
    """One answer as a CSV cell: a number, the masked text or the choices joined by "; "."""
    if answer is None:
        return ""
    if answer["value_number"] is not None:
        return str(_number(answer["value_number"]))
    if answer["value_choices"] is not None:
        return _csv_text("; ".join(answer["value_choices"]))
    return _csv_text(answer["text"] or "")


def csv_rows(
    questions: list[dict[str, Any]], rows: list[dict[str, Any]], labels: dict[str, str]
) -> list[list[str]]:
    """The header and one line per response: ID, Received, Segment, then each question."""
    lines = [["ID", "Received", "Segment", *(_csv_text(q["prompt"]) for q in questions)]]
    for row in rows:
        lines.append(
            [
                display_id(row["id"]),
                row["submitted_at"].astimezone(TIME_ZONE).isoformat(timespec="seconds"),
                labels.get(row["segment"], ""),
                *(csv_cell(row["answers"].get(q["id"])) for q in questions),
            ]
        )
    return lines
