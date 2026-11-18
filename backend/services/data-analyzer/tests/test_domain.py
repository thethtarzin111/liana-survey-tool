"""Results rules: segment grouping, per-kind scores and months."""

from datetime import UTC, datetime

from data_analyzer.domain import month_of, score, segment_groups, stored_segments


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
