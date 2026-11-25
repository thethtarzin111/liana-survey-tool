"""Comment insights rules: plain Python, no framework code.

The pipeline for one survey:

1. Collect the comments (`collect`).
2. Redact personal data: emails and phone numbers become "[hidden]".
3. Fewer than DIRECT_LIMIT comments: skip steps 4 and 5, one LLM batch.
4-5. Otherwise the grouper embeds and clusters the comments (see ports.CommentGrouper).
6. The theme writer (the LLM) names a theme, a summary and a quote per comment, one
   call per group. Clear scores decide the sentiment; the LLM only for mixed ones.
7. Code counts, computes percentages, sentiment and score comparisons, and keeps a
   quote only when it is found word-for-word in its comment (`analyse`).
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from liana_survey_shared.scoring import percent

from ..domain import MIN_GROUP, mask, score
from .ports import CommentGrouper, ThemeWriter

#: With fewer comments, grouping is skipped and the LLM reads them all in one batch.
DIRECT_LIMIT = 50
#: With fewer comments there is nothing to group: the tab says so instead.
MIN_COMMENTS = 5
MAX_QUOTES = 3
MAX_SAMPLES = 5
MAX_THEME_LENGTH = 60
OTHER = "Other"
SENTIMENTS = ("negative", "neutral", "positive")


@dataclass(frozen=True)
class Comment:
    comment_id: str
    #: Redacted text, the only text the AI steps and the admin app see.
    text: str
    #: The response's answer to the survey's main scale question, if any.
    answer: int | None


def collect(rows: list[dict[str, Any]]) -> tuple[list[Comment], int]:
    """Comments with short ids ("C1", "C2"…) from rows of {"text", "answer"}, blank ones
    left out, and how many had personal data redacted."""
    comments: list[Comment] = []
    redacted = 0
    for row in rows:
        text = (row["text"] or "").strip()
        if not text:
            continue
        text, was_masked = mask(text)
        redacted += was_masked
        answer = row["answer"]
        comments.append(
            Comment(f"C{len(comments) + 1}", text, int(answer) if answer is not None else None)
        )
    return comments, redacted


def sentiment_from_answer(kind: str | None, answer: int | None) -> str | None:
    """The sentiment a clear score gives, None when the score is mixed or missing
    (then the LLM decides). NPS 0-6 / 9-10, thumbs 0 / 2, rating 1-2 / 4-5."""
    if answer is None:
        return None
    if kind == "nps":
        return "negative" if answer <= 6 else "positive" if answer >= 9 else None
    if kind == "thumbs":
        return {0: "negative", 2: "positive"}.get(answer)
    if kind == "rating":
        return "negative" if answer <= 2 else "positive" if answer >= 4 else None
    return None


def _text(value: Any, limit: int | None = None) -> str:
    """A cleaned string from the LLM's JSON, empty when it is not a string."""
    if not isinstance(value, str):
        return ""
    value = " ".join(value.split())
    return value[:limit] if limit else value


def _scored(kind: str | None, comments: list[Comment]) -> int | None:
    """The main score of the comments' answers. None without a scale, or with fewer
    than MIN_GROUP scored answers, which would be too few to compare (and to keep
    anonymous)."""
    answers = [c.answer for c in comments if c.answer is not None]
    if kind is None or len(answers) < MIN_GROUP:
        return None
    counts: dict[int, int] = defaultdict(int)
    for answer in answers:
        counts[answer] += 1
    return score(kind, counts)


def analyse(
    comments: list[Comment],
    kind: str | None,
    known_themes: list[str],
    grouper: CommentGrouper,
    writer: ThemeWriter,
) -> dict[str, Any]:
    """Themes of the comments with every number computed here. `kind` is the main
    question's scale (nps, thumbs, rating) or None."""
    total = len(comments)
    run = {"grouper": None, "writer": writer.name, "llm_calls": 0}
    if total < MIN_COMMENTS:
        return {"status": "too_few", "mode": None, "themes": [], "negative_themes": [], "run": run}

    if total < DIRECT_LIMIT:
        mode, labels = "direct", [0] * total
    else:
        mode, labels = "clustered", grouper.group([c.text for c in comments])
        run["grouper"] = grouper.name
        if len(labels) != total:
            raise ValueError("The grouper must return one group per comment")

    batches: dict[int, list[Comment]] = defaultdict(list)
    for comment, label in zip(comments, labels, strict=True):
        batches[label].append(comment)

    # Step 6, one LLM call per group. Comments that fit no group skip the LLM.
    drafts: dict[str, dict[str, str]] = {}
    for label in sorted(batches):
        if label < 0:
            continue
        batch = batches[label]
        items = writer.describe(
            [{"comment_id": c.comment_id, "text": c.text} for c in batch], known_themes
        )
        run["llm_calls"] += 1
        ids = {c.comment_id for c in batch}
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict) or item.get("comment_id") not in ids:
                continue
            drafts.setdefault(
                item["comment_id"],
                {
                    "theme": _text(item.get("theme"), MAX_THEME_LENGTH) or OTHER,
                    "sentiment": _text(item.get("sentiment")).lower(),
                    "summary": _text(item.get("summary"), 300),
                    "quote": _text(item.get("quote")),
                },
            )

    # Step 7. Themes with the same name (any case) are one theme, so groups that the
    # LLM matched to the same existing theme are merged.
    themes: dict[str, dict[str, Any]] = {}
    for comment in comments:
        draft = drafts.get(comment.comment_id, {})
        label = draft.get("theme", OTHER)
        theme = themes.setdefault(
            label.casefold(), {"label": label, "comments": [], "sentiment": {}, "drafts": []}
        )
        sentiment = sentiment_from_answer(kind, comment.answer) or draft.get("sentiment")
        theme["comments"].append(comment)
        theme["sentiment"][comment.comment_id] = sentiment if sentiment in SENTIMENTS else "neutral"
        theme["drafts"].append(draft)

    overall = _scored(kind, comments)
    result = []
    for key, theme in themes.items():
        members: list[Comment] = theme["comments"]
        split = {s: 0 for s in SENTIMENTS}
        for sentiment in theme["sentiment"].values():
            split[sentiment] += 1
        quotes, hidden = [], 0
        for comment, draft in zip(members, theme["drafts"], strict=True):
            quote = draft.get("quote", "")
            if not quote:
                continue
            # The quote's whitespace is collapsed (_text), so compare it with the comment
            # collapsed the same way: a line break or double space is not a difference.
            if quote not in " ".join(comment.text.split()):
                hidden += 1
            elif len(quotes) < MAX_QUOTES and all(q["text"] != quote for q in quotes):
                quotes.append(
                    {"comment_id": comment.comment_id, "text": quote, "summary": draft["summary"]}
                )
        theme_score = _scored(kind, members)
        result.append(
            {
                "key": key,
                "label": theme["label"],
                "outlier": key == OTHER.casefold(),
                "comments": len(members),
                "percent": percent(len(members), total),
                "sentiment": split,
                "score": theme_score,
                "score_vs_all": (
                    theme_score - overall
                    if theme_score is not None and overall is not None
                    else None
                ),
                "quotes": quotes,
                "hidden_quotes": hidden,
                "samples": list(dict.fromkeys(c.text for c in members))[:MAX_SAMPLES],
            }
        )
    result.sort(key=lambda t: (t["outlier"], -t["comments"], t["label"].casefold()))

    negative_total = sum(t["sentiment"]["negative"] for t in result)
    negative = sorted(
        (t for t in result if not t["outlier"] and t["sentiment"]["negative"]),
        key=lambda t: (-t["sentiment"]["negative"], t["label"].casefold()),
    )[:3]
    return {
        "status": "ready",
        "mode": mode,
        "score": overall,
        "themes": result,
        "negative_themes": [
            {
                "key": t["key"],
                "label": t["label"],
                "count": t["sentiment"]["negative"],
                "percent": percent(t["sentiment"]["negative"], negative_total),
            }
            for t in negative
        ],
        "run": run,
    }
