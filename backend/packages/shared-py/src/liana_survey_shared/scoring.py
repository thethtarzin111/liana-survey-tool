"""Standard scores (#22): thumbs, NPS and CSAT, the answer split and top reasons.

Plain functions, no framework code, so Liana can translate them later. Shared by
the worker (which keeps the totals) and the services that show results.

Counts come as a mapping from answer value to number of answers, the shape the
worker stores in survey_aggregates.distribution, e.g. {"0": 3, "9": 12}. Keys may
be strings or ints. Percentages are whole numbers, rounded half up, as in the
prototype; scores are None when there are no answers yet.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

Counts = Mapping[str | int, int]

THUMBS_SCALE = (0, 1, 2)  # Not for me, Good, Loved it
NPS_SCALE = tuple(range(0, 11))
CSAT_SCALE = (1, 2, 3, 4, 5)


def _counts(counts: Counts, scale: Iterable[int]) -> dict[int, int]:
    """Counts per scale value (missing values are 0). Values outside the scale are ignored."""
    by_value = {int(value): int(n) for value, n in counts.items()}
    return {value: by_value.get(value, 0) for value in scale}


def percent(part: int, total: int) -> int | None:
    """Whole percent, rounded half up (2.5 -> 3). None when total is 0."""
    if total <= 0:
        return None
    return int((Decimal(part) * 100 / Decimal(total)).quantize(Decimal(1), ROUND_HALF_UP))


# --- Thumbs ----------------------------------------------------------------------


@dataclass(frozen=True)
class ThumbsScore:
    total: int
    #: % Good + Loved it.
    positive: int | None
    #: % Loved it.
    loved_it: int | None


def thumbs_score(counts: Counts) -> ThumbsScore:
    c = _counts(counts, THUMBS_SCALE)
    total = sum(c.values())
    return ThumbsScore(total, percent(c[1] + c[2], total), percent(c[2], total))


# --- NPS -------------------------------------------------------------------------


@dataclass(frozen=True)
class NpsScore:
    total: int
    promoters: int  # 9-10
    passives: int  # 7-8
    detractors: int  # 0-6
    #: % promoters - % detractors, -100 to +100.
    score: int | None


def nps_score(counts: Counts) -> NpsScore:
    c = _counts(counts, NPS_SCALE)
    promoters = c[9] + c[10]
    passives = c[7] + c[8]
    detractors = sum(c[v] for v in range(0, 7))
    total = promoters + passives + detractors
    score = None
    if total:
        exact = (Decimal(promoters) - Decimal(detractors)) * 100 / Decimal(total)
        # Round half away from zero, so +42.5 -> +43 and -42.5 -> -43.
        score = int(exact.quantize(Decimal(1), ROUND_HALF_UP))
    return NpsScore(total, promoters, passives, detractors, score)


# --- CSAT ------------------------------------------------------------------------


@dataclass(frozen=True)
class CsatScore:
    total: int
    #: % of 4-5 answers.
    satisfied: int | None
    #: Average on the 1-5 scale, one decimal.
    average: float | None


def csat_score(counts: Counts) -> CsatScore:
    c = _counts(counts, CSAT_SCALE)
    total = sum(c.values())
    if not total:
        return CsatScore(0, None, None)
    weighted = sum(value * n for value, n in c.items())
    average = float((Decimal(weighted) / Decimal(total)).quantize(Decimal("0.1"), ROUND_HALF_UP))
    return CsatScore(total, percent(c[4] + c[5], total), average)


# --- Split and reasons -------------------------------------------------------------


@dataclass(frozen=True)
class Share:
    value: str | int
    count: int
    percent: int | None


def answer_split(counts: Counts, scale: Iterable[int]) -> list[Share]:
    """Every scale value with its count and percent, in scale order."""
    c = _counts(counts, scale)
    total = sum(c.values())
    return [Share(value, n, percent(n, total)) for value, n in c.items()]


def top_reasons(
    reason_counts: Mapping[str, int], respondents: int, limit: int | None = None
) -> list[Share]:
    """Reasons by how often they were picked, most first (ties by name).

    Percent is of the respondents who were asked, since readers can pick more
    than one reason ("Why 34 readers chose 'Not for me'": 12 said too long)."""
    picked = [(reason, n) for reason, n in reason_counts.items() if n > 0]
    picked.sort(key=lambda item: (-item[1], item[0].casefold()))
    if limit is not None:
        picked = picked[:limit]
    return [Share(reason, n, percent(n, respondents)) for reason, n in picked]


# --- Headline score (Surveys list) ---------------------------------------------------


@dataclass(frozen=True)
class Headline:
    score: str
    note: str


def headline(survey_type: str, counts: Counts) -> Headline | None:
    """The Surveys list's "Headline score" for a survey's main question, worded as
    in the prototype. None for custom surveys and before the first answer."""
    if survey_type == "thumbs":
        t = thumbs_score(counts)
        if t.total:
            return Headline(f"{t.positive}% positive", f"{t.loved_it}% loved it")
    elif survey_type == "nps":
        n = nps_score(counts)
        if n.score is not None:
            sign = "+" if n.score > 0 else ""
            return Headline(f"NPS {sign}{n.score}", "scale −100 to +100")
    elif survey_type == "csat":
        s = csat_score(counts)
        if s.total:
            return Headline(f"{s.satisfied}% satisfied", f"{s.average:.1f} average")
    return None
