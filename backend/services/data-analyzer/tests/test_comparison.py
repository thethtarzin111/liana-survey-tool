from data_analyzer.domain import compare_scores


def test_segment_and_month_scores_use_combined_counts():
    rows = [
        {"segment": "members", "month": "2026-01-01", "value_number": 10, "count": 3},
        {"segment": "partners", "month": "2026-01-01", "value_number": 0, "count": 1},
    ]
    result = compare_scores("nps", rows)
    assert result["months"][0]["score"] == 50
    assert [point["score"] for point in result["segments"]] == [100, -100]


def test_empty_comparison():
    assert compare_scores("nps", []) == {"segments": [], "months": []}
