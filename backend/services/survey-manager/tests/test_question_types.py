"""Answer-type rules (#30): what each question type needs and which answers it accepts.

The domain tests run anywhere; the API tests marked `db` need a database (see test_surveys.py).
"""

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from liana_survey_shared.db import ping
from liana_survey_shared.web.db import tenant_db
from survey_manager.main import app
from survey_manager.questions.domain import (
    AnswerError,
    QuestionRuleError,
    check_answer,
    check_options,
    options_after_change,
)
from survey_manager.questions.schemas import QuestionKind as K

needs_db = pytest.mark.skipif(
    not os.environ.get("REQUIRE_DB") and not ping(), reason="no database (set DATABASE_URL)"
)
CHOICE = [K.single_choice, K.multiple_choice, K.dropdown, K.reasons]
NO_OPTIONS = [K.text, K.long_text, K.rating, K.nps]


# --- Question config ----------------------------------------------------------


@pytest.mark.parametrize("kind", CHOICE)
def test_choice_types_need_distinct_non_blank_options(kind):
    assert check_options(kind, ["  Price ", "Quality"]) == ["Price", "Quality"]
    for bad in ([], [""], ["  "], ["Price", "price"], [1, 2], [None], ["x" * 201], ["o"] * 21):
        with pytest.raises(QuestionRuleError):
            check_options(kind, bad)
    assert len(check_options(kind, [f"Option {n}" for n in range(20)])) == 20


@pytest.mark.parametrize("kind", NO_OPTIONS)
def test_text_and_scale_types_have_no_options(kind):
    assert check_options(kind, []) == []
    with pytest.raises(QuestionRuleError):
        check_options(kind, ["1"])


def test_changing_type_keeps_or_clears_options():
    # Options left out stay when the new type uses them...
    assert options_after_change(K.single_choice, ["A", "B"], K.dropdown, None) == ["A", "B"]
    # ...and are cleared when it does not.
    assert options_after_change(K.single_choice, ["A", "B"], K.nps, None) == []
    # A choice type needs options from somewhere.
    with pytest.raises(QuestionRuleError):
        options_after_change(K.text, [], K.multiple_choice, None)
    assert options_after_change(K.text, [], K.reasons, ["Price"]) == ["Price"]


# --- Answers ------------------------------------------------------------------


@pytest.mark.parametrize("kind", [K.single_choice, K.dropdown])
def test_pick_one_answers(kind):
    options = ["Yes", "No"]
    assert check_answer(kind, options, True, "Yes") == "Yes"
    for bad in ("Maybe", ["Yes"], 1):
        with pytest.raises(AnswerError):
            check_answer(kind, options, True, bad)


@pytest.mark.parametrize("kind", [K.multiple_choice, K.reasons])
def test_pick_any_answers(kind):
    options = ["Price", "Quality", "Service"]
    assert check_answer(kind, options, True, ["Price", "Service"]) == ["Price", "Service"]
    for bad in ("Price", ["Price", "Price"], ["Speed"], [1]):
        with pytest.raises(AnswerError):
            check_answer(kind, options, True, bad)


@pytest.mark.parametrize(("kind", "low", "high"), [(K.rating, 1, 5), (K.nps, 0, 10)])
def test_scale_answers(kind, low, high):
    assert check_answer(kind, [], True, low) == low
    assert check_answer(kind, [], True, high) == high
    for bad in (low - 1, high + 1, 2.5, "3", True):
        with pytest.raises(AnswerError):
            check_answer(kind, [], True, bad)


@pytest.mark.parametrize(("kind", "limit"), [(K.text, 500), (K.long_text, 5000)])
def test_text_answers(kind, limit):
    assert check_answer(kind, [], True, "  Great event  ") == "Great event"
    assert check_answer(kind, [], True, "x" * limit) == "x" * limit
    for bad in ("x" * (limit + 1), 5, ["text"]):
        with pytest.raises(AnswerError):
            check_answer(kind, [], True, bad)


@pytest.mark.parametrize("kind", list(K))
def test_required_questions_need_an_answer_and_optional_ones_do_not(kind):
    options = ["A"] if kind in CHOICE else []
    for empty in (None, "", []):
        with pytest.raises(AnswerError):
            check_answer(kind, options, True, empty)
        assert check_answer(kind, options, False, empty) is None
    if kind in (K.text, K.long_text):
        assert check_answer(kind, [], False, "   ") is None


# --- API ----------------------------------------------------------------------


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def no_db(client):
    app.dependency_overrides[tenant_db] = lambda: None
    return client


@pytest.mark.parametrize(
    "body",
    [
        {"kind": "text", "options": ["A"]},  # text has no options
        {"kind": "rating", "options": ["1", "2"]},  # fixed scale
        {"kind": "single_choice"},  # choice needs options
        {"kind": "dropdown", "options": ["A", "a"]},  # duplicates
        {"kind": "reasons", "options": [""]},  # blank
        {"kind": "multiple_choice", "options": [1, 2]},  # not text
        {"kind": "text", "prompt": "x" * 501},  # prompt too long
    ],
)
def test_add_rejects_options_that_do_not_fit_the_type(no_db, body):
    r = no_db.post(f"/api/v1/surveys/{uuid4()}/questions", json=body)
    assert r.status_code == 422


@pytest.mark.db
@needs_db
@pytest.mark.parametrize("kind", list(K))
def test_every_answer_type_can_be_added(client, kind):
    survey_id = client.post("/api/v1/surveys", json={"type": "custom"}).json()["id"]
    body = {"kind": kind.value, "prompt": "  Your view?  "}
    if kind in CHOICE:
        body["options"] = [" Option 1 ", "Option 2"]
    r = client.post(f"/api/v1/surveys/{survey_id}/questions", json=body)
    assert r.status_code == 201
    assert r.json()["kind"] == kind.value
    assert r.json()["prompt"] == "Your view?"
    assert r.json()["options"] == (["Option 1", "Option 2"] if kind in CHOICE else [])


@pytest.mark.db
@needs_db
def test_changing_type_checks_options_against_the_saved_question(client):
    survey_id = client.post("/api/v1/surveys", json={"type": "custom"}).json()["id"]
    base = f"/api/v1/surveys/{survey_id}/questions"
    question = client.post(base, json={"kind": "single_choice", "options": ["Yes", "No"]}).json()
    url = f"{base}/{question['id']}"

    # Keeps its options when switching between choice types.
    r = client.patch(url, json={"kind": "dropdown"})
    assert (r.status_code, r.json()["options"]) == (200, ["Yes", "No"])
    # Options alone must still fit the saved type.
    assert client.patch(url, json={"options": []}).status_code == 422
    # Switching to a scale clears them.
    r = client.patch(url, json={"kind": "nps"})
    assert (r.status_code, r.json()["options"]) == (200, [])
    # A scale cannot get options, and a choice type needs them.
    assert client.patch(url, json={"options": ["A"]}).status_code == 422
    r = client.patch(url, json={"kind": "reasons"})
    assert r.status_code == 422
    assert "at least one option" in r.json()["detail"]
    r = client.patch(url, json={"kind": "reasons", "options": ["Price", "Quality"]})
    assert (r.status_code, r.json()["options"]) == (200, ["Price", "Quality"])
    # Nothing was changed by the rejected edits.
    assert client.get(base).json()[0]["kind"] == "reasons"
