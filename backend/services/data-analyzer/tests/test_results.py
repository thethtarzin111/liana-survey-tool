from liana_survey_shared.scoring import NPS_SCALE, answer_split, headline


def test_summary_calculates_headline_and_full_answer_split():
    counts = {"3": 2, "8": 1, "9": 5, "10": 2}
    score = headline("nps", counts)
    split = answer_split(counts, NPS_SCALE)
    assert score and score.score == "NPS +50"
    assert sum(item.count for item in split) == 10
    assert [item.value for item in split] == list(range(11))


def test_summary_has_no_headline_or_percentages_without_answers():
    assert headline("nps", {}) is None
    assert all(item.percent is None for item in answer_split({}, NPS_SCALE))
