"""Comment insights rules: redaction, the direct/clustered switch, checks on the LLM's
JSON, and the numbers computed in code."""

import pytest

from data_analyzer.insights.adapters import (
    HdbscanGrouper,
    MockGrouper,
    MockThemeWriter,
    build_grouper,
    build_writer,
)
from data_analyzer.insights.domain import (
    DIRECT_LIMIT,
    MIN_COMMENTS,
    Comment,
    analyse,
    collect,
    sentiment_from_answer,
)
from liana_survey_shared.config import Settings


class FakeWriter:
    """Returns the items given per comment id, and records each batch it was sent."""

    name = "Fake LLM"

    def __init__(self, items=None, extra=()):
        self.items = items or {}
        self.extra = list(extra)
        self.batches = []

    def describe(self, comments, known_themes):
        self.batches.append([c["comment_id"] for c in comments])
        out = [self.items[c["comment_id"]] for c in comments if c["comment_id"] in self.items]
        return out + self.extra


class FakeGrouper:
    name = "Fake grouper"

    def __init__(self, labels):
        self.labels = labels

    def group(self, texts):
        return self.labels


def item(comment_id, theme, quote="", sentiment="neutral", summary="Sum."):
    return {
        "comment_id": comment_id,
        "theme": theme,
        "sentiment": sentiment,
        "summary": summary,
        "quote": quote,
    }


def comments(answers, text="Delivery took too long"):
    return [Comment(f"C{i + 1}", f"{text} {i}", a) for i, a in enumerate(answers)]


def test_collect_redacts_and_numbers_comments():
    rows = [
        {"text": "Call me on +358 40 123 4567", "answer": 3},
        {"text": "   ", "answer": 9},
        {"text": None, "answer": 9},
        {"text": "Write to anna.virtanen@example.org", "answer": None},
        {"text": "Great events", "answer": 10},
    ]
    found, redacted = collect(rows)
    assert [(c.comment_id, c.text, c.answer) for c in found] == [
        ("C1", "Call me on [hidden]", 3),
        ("C2", "Write to [hidden]", None),
        ("C3", "Great events", 10),
    ]
    assert redacted == 2


@pytest.mark.parametrize(
    "kind, answer, expected",
    [
        ("nps", 0, "negative"),
        ("nps", 6, "negative"),
        ("nps", 7, None),
        ("nps", 8, None),
        ("nps", 9, "positive"),
        ("thumbs", 0, "negative"),
        ("thumbs", 1, None),
        ("thumbs", 2, "positive"),
        ("rating", 2, "negative"),
        ("rating", 3, None),
        ("rating", 4, "positive"),
        ("nps", None, None),
        (None, 5, None),
    ],
)
def test_sentiment_comes_from_clear_scores_only(kind, answer, expected):
    assert sentiment_from_answer(kind, answer) == expected


def test_too_few_comments_make_no_llm_call():
    writer = FakeWriter()
    result = analyse(comments([5] * (MIN_COMMENTS - 1)), "nps", [], MockGrouper(), writer)
    assert result["status"] == "too_few"
    assert result["themes"] == []
    assert writer.batches == []


def test_fewer_than_the_limit_is_one_batch_without_grouping():
    class NoGrouper:
        name = "unused"

        def group(self, texts):
            raise AssertionError("grouping must be skipped")

    writer = FakeWriter()
    result = analyse(comments([5] * (DIRECT_LIMIT - 1)), "nps", [], NoGrouper(), writer)
    assert result["mode"] == "direct"
    assert len(writer.batches) == 1 and len(writer.batches[0]) == DIRECT_LIMIT - 1
    assert result["run"] == {"grouper": None, "writer": "Fake LLM", "llm_calls": 1}


def test_clustered_calls_the_llm_per_group_and_skips_outliers():
    found = comments([5] * DIRECT_LIMIT)
    labels = [0] * 20 + [1] * 20 + [-1] * 10
    items = {c.comment_id: item(c.comment_id, "Slow delivery") for c in found[:20]}
    items |= {c.comment_id: item(c.comment_id, "slow DELIVERY") for c in found[20:40]}
    writer = FakeWriter(items)
    result = analyse(found, "nps", [], FakeGrouper(labels), writer)
    assert result["mode"] == "clustered"
    assert [len(b) for b in writer.batches] == [20, 20]
    assert result["run"]["llm_calls"] == 2
    assert result["run"]["grouper"] == "Fake grouper"
    # Two groups the LLM gave the same theme (any case) are one theme; noise is Other.
    assert [(t["label"], t["comments"], t["outlier"]) for t in result["themes"]] == [
        ("Slow delivery", 40, False),
        ("Other", 10, True),
    ]


def test_grouper_must_label_every_comment():
    with pytest.raises(ValueError):
        analyse(comments([5] * DIRECT_LIMIT), "nps", [], FakeGrouper([0]), FakeWriter())


def test_counts_percentages_and_sentiment_are_computed_in_code():
    # NPS answers: 2 detractors, 2 passives, 2 promoters in "Price"; 2 more in "Events".
    found = comments([0, 3, 7, 8, 9, 10, 10, 10])
    items = {
        "C1": item("C1", "Price", sentiment="positive"),  # a clear score wins
        "C2": item("C2", "Price"),
        "C3": item("C3", "Price", sentiment="negative"),  # mixed score: the LLM decides
        "C4": item("C4", "Price", sentiment="nonsense"),  # unknown: neutral
        "C5": item("C5", "Price"),
        "C6": item("C6", "Price"),
        "C7": item("C7", "Events"),
        "C8": item("C8", "Events"),
    }
    result = analyse(found, "nps", [], MockGrouper(), FakeWriter(items))
    price, events = result["themes"]
    assert (price["label"], price["comments"], price["percent"]) == ("Price", 6, 75)
    assert price["sentiment"] == {"negative": 3, "neutral": 1, "positive": 2}
    assert events["sentiment"] == {"negative": 0, "neutral": 0, "positive": 2}
    # NPS of commenters: 4 promoters, 2 detractors of 8 = +25; Price: 2 - 2 of 6 = 0.
    assert result["score"] == 25
    assert price["score"] == 0 and price["score_vs_all"] == -25
    # Too few scored answers for a score of its own.
    assert events["score"] is None and events["score_vs_all"] is None
    assert result["negative_themes"] == [
        {"key": "price", "label": "Price", "count": 3, "percent": 100}
    ]


def test_comments_the_llm_skipped_or_invented_are_handled():
    found = comments([5] * 6)
    items = {"C1": item("C1", "Price"), "C2": item("C2", "  ")}
    extra = [item("C99", "Invented"), "not a dict", item("C1", "Duplicate")]
    result = analyse(found, None, [], MockGrouper(), FakeWriter(items, extra))
    labels = {t["label"]: t["comments"] for t in result["themes"]}
    assert labels == {"Price": 1, "Other": 5}
    assert result["score"] is None


def test_only_word_for_word_quotes_are_kept():
    found = [
        Comment("C1", "The sofa arrived nine days late", 2),
        Comment("C2", "Toimitus myöhästyi viikolla", 3),
        Comment("C3", "Delivery was slow", 4),
        Comment("C4", "Slow, slow, slow", 1),
        Comment("C5", "No quote here", 0),
    ]
    items = {
        "C1": item("C1", "Delivery", quote="arrived nine days late", summary="Late sofa."),
        "C2": item("C2", "Delivery", quote="Toimitus myöhästyi viikolla"),
        "C3": item("C3", "Delivery", quote="Delivery was very slow"),  # not in the comment
        "C4": item("C4", "Delivery", quote="slow, SLOW"),  # case differs
        "C5": item("C5", "Delivery", quote=""),
    }
    theme = analyse(found, "nps", [], MockGrouper(), FakeWriter(items))["themes"][0]
    assert theme["quotes"] == [
        {"comment_id": "C1", "text": "arrived nine days late", "summary": "Late sofa."},
        {"comment_id": "C2", "text": "Toimitus myöhästyi viikolla", "summary": "Sum."},
    ]
    assert theme["hidden_quotes"] == 2


def test_mock_writer_uses_the_surveys_reasons_and_real_quotes():
    batch = [
        {"comment_id": "C1", "text": "Membership price went up and I am not sure it is worth it."},
        {"comment_id": "C2", "text": "Hinta on liian korkea."},
        {"comment_id": "C3", "text": "The autumn events were well organised."},
        {"comment_id": "C4", "text": "ok"},
    ]
    out = MockThemeWriter().describe(batch, ["Events", "Membership fee"])
    assert [i["theme"] for i in out] == ["Membership fee", "Membership fee", "Events", "Other"]
    for source, result in zip(batch, out, strict=True):
        assert result["quote"] in source["text"]


def test_adapters_are_picked_from_settings():
    assert isinstance(build_grouper(Settings(insights_grouper="mock")), MockGrouper)
    assert isinstance(build_grouper(Settings(insights_grouper="hdbscan")), HdbscanGrouper)
    assert isinstance(build_writer(Settings(insights_writer="mock")), MockThemeWriter)
    with pytest.raises(ValueError):
        build_writer(Settings(insights_writer="unknown"))


def test_hdbscan_finds_the_number_of_groups_itself():
    np = pytest.importorskip("numpy")
    pytest.importorskip("sklearn")
    from data_analyzer.insights.adapters import cluster

    rng = np.random.default_rng(1)
    centres = [(0, 0), (10, 0), (0, 10)]
    points = np.vstack([rng.normal(c, 0.3, size=(20, 2)) for c in centres])
    labels = cluster(points, min_cluster_size=5)
    assert len(labels) == 60
    assert len({label for label in labels if label >= 0}) == 3


def test_repeated_comments_give_distinct_quotes_and_samples():
    found = [Comment(f"C{i}", "Hard to find information", 3) for i in range(1, 6)]
    found.append(Comment("C6", "Website is slow", 3))
    items = {c.comment_id: item(c.comment_id, "Website", quote=c.text) for c in found}
    theme = analyse(found, "nps", [], MockGrouper(), FakeWriter(items))["themes"][0]
    assert [q["text"] for q in theme["quotes"]] == ["Hard to find information", "Website is slow"]
    assert theme["samples"] == ["Hard to find information", "Website is slow"]
    assert theme["comments"] == 6


def test_a_quote_across_a_line_break_or_double_space_is_still_word_for_word():
    # From review: the quote is whitespace-collapsed, so the comment is compared the
    # same way; only the words must match.
    found = [
        Comment("C1", "Delivery took\nnine days.  Far too long", 2),
        Comment("C2", "Price  is fine", 8),
        # Enough comments for themes; these have no quote.
        *(Comment(f"C{i}", f"Other comment {i}", 5) for i in range(3, 6)),
    ]
    items = {
        "C1": item("C1", "Delivery", quote="took nine days. Far too long", summary="Late."),
        "C2": item("C2", "Delivery", quote="Price   is\tfine"),
        **{f"C{i}": item(f"C{i}", "Delivery", quote="") for i in range(3, 6)},
    }
    theme = analyse(found, "nps", [], MockGrouper(), FakeWriter(items))["themes"][0]
    assert [q["text"] for q in theme["quotes"]] == ["took nine days. Far too long", "Price is fine"]
    assert theme["hidden_quotes"] == 0
