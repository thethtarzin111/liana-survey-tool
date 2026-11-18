from data_analyzer.performance import response_rate


def test_response_rate_is_responses_divided_by_views():
    assert response_rate(25, 100) == 25
    assert response_rate(2, 3) == 67


def test_response_rate_has_no_value_without_views():
    assert response_rate(0, 0) is None
    assert response_rate(3, 0) is None
