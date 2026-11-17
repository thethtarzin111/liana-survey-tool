import pytest

from liana_survey_shared.scoring import (
    CSAT_SCALE,
    NPS_SCALE,
    THUMBS_SCALE,
    Headline,
    Share,
    answer_split,
    csat_score,
    headline,
    nps_score,
    percent,
    thumbs_score,
    top_reasons,
)


def test_percent_rounds_half_up_and_is_none_without_answers():
    assert percent(1, 3) == 33
    assert percent(2, 3) == 67
    assert percent(1, 8) == 13  # 12.5 -> 13
    assert percent(0, 5) == 0
    assert percent(3, 0) is None


# --- Thumbs ----------------------------------------------------------------------


def test_thumbs_positive_and_loved_it():
    # The prototype's newsletter: 16% not for me, 53% good, 31% loved it.
    score = thumbs_score({"0": 34, "1": 113, "2": 66})
    assert (score.total, score.positive, score.loved_it) == (213, 84, 31)


def test_thumbs_without_answers():
    assert thumbs_score({}) == thumbs_score({"0": 0})
    assert (thumbs_score({}).positive, thumbs_score({}).loved_it) == (None, None)


def test_thumbs_all_one_answer():
    assert (thumbs_score({0: 5}).positive, thumbs_score({0: 5}).loved_it) == (0, 0)
    assert (thumbs_score({2: 5}).positive, thumbs_score({2: 5}).loved_it) == (100, 100)


# --- NPS -------------------------------------------------------------------------


def test_nps_groups_and_score():
    counts = {"0": 1, "6": 2, "7": 1, "8": 1, "9": 3, "10": 2}
    score = nps_score(counts)
    assert (score.detractors, score.passives, score.promoters, score.total) == (3, 2, 5, 10)
    assert score.score == 20  # 50% promoters - 30% detractors


@pytest.mark.parametrize(
    ("counts", "expected"),
    [
        ({"10": 4}, 100),
        ({"0": 4}, -100),
        ({"7": 3, "8": 3}, 0),  # only passives
        ({"9": 1, "6": 1}, 0),
        ({"9": 17, "5": 23, "7": 40}, -8),  # -7.5 rounds away from zero
        ({"10": 17, "7": 63}, 21),  # 21.25
    ],
)
def test_nps_edges(counts, expected):
    assert nps_score(counts).score == expected


def test_nps_without_answers():
    assert nps_score({}).score is None
    assert nps_score({}).total == 0


# --- CSAT ------------------------------------------------------------------------


def test_csat_satisfied_and_average():
    score = csat_score({"1": 2, "2": 3, "3": 5, "4": 20, "5": 20})
    assert (score.total, score.satisfied, score.average) == (50, 80, 4.1)


def test_csat_edges():
    assert (csat_score({"5": 3}).satisfied, csat_score({"5": 3}).average) == (100, 5.0)
    assert (csat_score({"1": 1}).satisfied, csat_score({"1": 1}).average) == (0, 1.0)
    assert csat_score({"4": 1, "5": 1}).average == 4.5  # rounds half up


def test_csat_without_answers():
    assert csat_score({}) == csat_score({"3": 0})
    assert (csat_score({}).satisfied, csat_score({}).average) == (None, None)


# --- Split and reasons -------------------------------------------------------------


def test_answer_split_lists_every_scale_value_in_order():
    split = answer_split({"1": 1, "2": 3}, THUMBS_SCALE)
    assert split == [Share(0, 0, 0), Share(1, 1, 25), Share(2, 3, 75)]
    assert [s.value for s in answer_split({}, NPS_SCALE)] == list(range(11))
    assert all(s.percent is None for s in answer_split({}, CSAT_SCALE))


def test_answer_split_ignores_values_outside_the_scale():
    assert answer_split({"7": 4, "5": 1}, CSAT_SCALE)[-1] == Share(5, 1, 100)


def test_top_reasons_are_sorted_and_counted_against_respondents():
    reasons = {
        "Too long": 12,
        "Not relevant to me": 9,
        "Something else": 7,
        "Too often": 6,
        "Unused": 0,
    }
    top = top_reasons(reasons, respondents=34)
    assert [r.value for r in top] == [
        "Too long",
        "Not relevant to me",
        "Something else",
        "Too often",
    ]
    assert top[0] == Share("Too long", 12, 35)
    assert [r.value for r in top_reasons(reasons, 34, limit=2)] == [
        "Too long",
        "Not relevant to me",
    ]


def test_top_reasons_ties_are_alphabetical_and_empty_is_empty():
    assert [r.value for r in top_reasons({"b": 2, "A": 2}, 4)] == ["A", "b"]
    assert top_reasons({}, 0) == []
    assert top_reasons({"x": 1}, 0) == [Share("x", 1, None)]


# --- Headline score ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("survey_type", "counts", "expected"),
    [
        ("thumbs", {"0": 34, "1": 113, "2": 66}, Headline("84% positive", "31% loved it")),
        ("nps", {"9": 6, "6": 1, "7": 3}, Headline("NPS +50", "scale −100 to +100")),
        ("nps", {"0": 3, "9": 1}, Headline("NPS -50", "scale −100 to +100")),
        ("nps", {"8": 2}, Headline("NPS 0", "scale −100 to +100")),
        ("csat", {"5": 2, "4": 2, "2": 1}, Headline("80% satisfied", "4.0 average")),
    ],
)
def test_headline_wording_matches_the_prototype(survey_type, counts, expected):
    assert headline(survey_type, counts) == expected


def test_no_headline_for_custom_surveys_or_before_answers():
    assert headline("custom", {"1": 3}) is None
    for survey_type in ("thumbs", "nps", "csat"):
        assert headline(survey_type, {}) is None
