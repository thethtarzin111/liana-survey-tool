"""Results rules: segment grouping, per-kind scores and months."""

from datetime import UTC, datetime

from data_analyzer.domain import month_of, overview, score, segment_groups, stored_segments


def test_segment_groups_threshold():
    groups = segment_groups({"members": 5, "partners": 4, "volunteers": 3, "all": 6})
    assert [(g.value, g.label, g.answers) for g in groups] == [
        ("none", "No segment", 6),
        ("members", "Members", 5),
        ("other", "Other", 7),
    ]
    assert stored_segments(groups, "other") == ("partners", "volunteers")
    assert stored_segments(groups, "partners") is None


def test_small_other_is_not_shown():
    assert [g.value for g in segment_groups({"members": 9, "partners": 2})] == ["members"]


def test_stored_segments_maps_the_filter_values():
    groups = segment_groups({"members": 9, "all": 5})
    assert stored_segments(groups, "none") == ("all",)
    assert stored_segments(groups, "members") == ("members",)
    assert stored_segments(groups, "unknown") is None


def test_score_per_kind():
    assert score("nps", {"0": 2, "10": 1}) == -33
    assert score("thumbs", {"0": 1, "1": 1, "2": 2}) == 75
    assert score("rating", {"2": 1, "4": 1, "5": 2}) == 75
    assert score("single_choice", {"a": 1}) is None


def test_month_uses_helsinki_time():
    assert month_of(datetime(2026, 10, 31, 22, 30, tzinfo=UTC)) == "2026-11"


def _custom_rows(questions, **extra):
    """Rows as repo.overview_rows returns them, for a custom survey answered 6 times."""
    return {
        "survey": {
            "id": "s1",
            "title": "Custom",
            "type": "custom",
            "status": "live",
            "closes_at": None,
            "last_answer_at": None,
        },
        "now": datetime(2026, 11, 19, 12, tzinfo=UTC),
        "channels": ["link"],
        "views": 12,
        "questions": questions,
        "segment_counts": {"all": 6},
        "answered": {},
        "values": {},
        "main_rows": [],
        "completed": 0,
        **extra,
    }


def _q(qid, kind, options=(), required=True):
    return {"id": qid, "kind": kind, "prompt": qid, "required": required, "options": list(options)}


def test_custom_survey_main_is_first_scale_question():
    rows = _custom_rows(
        [_q("pick", "single_choice", ["A", "B"]), _q("rate", "rating"), _q("nps", "nps")],
        answered={"pick": 6, "rate": 6, "nps": 6},
        values={"pick": {"A": 4, "B": 2}, "rate": {"5": 2, "4": 1, "2": 3}, "nps": {"10": 6}},
        main_rows=[
            {"segment": "all", "month": "2026-10", "value": "5", "n": 2},
            {"segment": "all", "month": "2026-10", "value": "2", "n": 1},
            {"segment": "all", "month": "2026-11", "value": "4", "n": 1},
            {"segment": "all", "month": "2026-11", "value": "2", "n": 2},
        ],
    )
    result = overview(rows, "all")
    assert result["main"]["question_id"] == "rate"
    assert result["main"]["kind"] == "rating"
    assert result["main"]["counts"] == {"1": 0, "2": 3, "3": 0, "4": 1, "5": 2}
    assert result["main"]["score"] == 50
    assert result["main"]["change"] == 50 - 67
    assert [(p["month"], p["answers"], p["score"]) for p in result["trend"]] == [
        ("2026-10", 3, 67),
        ("2026-11", 3, 33),
    ]
    questions = {q["id"]: q for q in result["questions"]}
    assert questions["pick"]["options"] == [
        {"label": "A", "count": 4},
        {"label": "B", "count": 2},
    ]
    assert questions["rate"]["average"] == 3.3
    assert result["response_rate"] == 50


def test_custom_survey_without_scale_has_no_main():
    rows = _custom_rows(
        [_q("pick", "single_choice", ["A"]), _q("why", "text")],
        answered={"pick": 6, "why": 2},
        values={"pick": {"A": 6}},
    )
    result = overview(rows, "all")
    assert result["main"] is None
    assert result["trend"] == []
    assert result["by_segment"] == []


def test_multiple_choice_counts_each_option_once_per_response():
    rows = _custom_rows(
        [_q("many", "multiple_choice", ["A", "B", "C"])],
        answered={"many": 4},
        values={"many": {"A": 4, "B": 1}},
    )
    question = overview(rows, "all")["questions"][0]
    assert question["answers"] == 4
    assert question["options"] == [
        {"label": "A", "count": 4},
        {"label": "B", "count": 1},
        {"label": "C", "count": 0},
    ]


def test_completed_all_counts_optional_questions():
    rows = _custom_rows(
        [_q("a", "text"), _q("b", "text", required=False)],
        completed=3,
    )
    assert overview(rows, "all")["completed_all"] == 50
    standard = _custom_rows([_q("a", "nps")], completed=6)
    standard["survey"]["type"] = "nps"
    assert overview(standard, "all")["completed_all"] is None


def test_change_is_hidden_without_earlier_answers():
    rows = _custom_rows(
        [_q("rate", "rating")],
        answered={"rate": 2},
        values={"rate": {"5": 2}},
        main_rows=[{"segment": "all", "month": "2026-11", "value": "5", "n": 2}],
    )
    result = overview(rows, "all")
    assert result["main"]["change"] is None
    assert result["trend"] == []


def test_segments_need_groups_that_cover_every_response():
    from data_analyzer.domain import available_groups, segments_enabled

    def enabled(counts):
        return segments_enabled(segment_groups(counts), sum(counts.values()))

    assert enabled({"members": 5, "partners": 4, "all": 3})  # Other 7 covers the rest
    assert enabled({"members": 5, "volunteers": 5})
    assert not enabled({"members": 10, "partners": 3})  # hidden Other
    assert not enabled({"members": 10, "all": 5, "partners": 3})
    assert not enabled({"members": 10})  # a single group
    assert not enabled({})
    assert available_groups({"members": 10, "partners": 3}) == []
    assert [g.value for g in available_groups({"members": 5, "volunteers": 5})] == [
        "members",
        "volunteers",
    ]
