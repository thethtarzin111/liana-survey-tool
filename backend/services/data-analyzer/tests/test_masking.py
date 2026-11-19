"""Masking of emails and phone numbers, and the short display id."""

import re
from uuid import UUID

import pytest

from data_analyzer.domain import GROUPS, display_id, mask


def test_mask_keeps_the_rest_of_the_comment():
    assert mask("Mail me at anna.virtanen@example.org thanks") == (
        "Mail me at [hidden] thanks",
        True,
    )
    assert mask("Call +358 40 123 4567 or 040-1234567") == ("Call [hidden] or [hidden]", True)
    assert mask("Room 12, 3 people, 2026") == ("Room 12, 3 people, 2026", False)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("0401234567", "[hidden]"),
        ("(09) 123 4567", "[hidden]"),
        ("tel 09 123 4567.", "tel [hidden]."),
        ("+44 20 7946 0958", "[hidden]"),
        ("00358 40 123 4567", "[hidden]"),
        ("a@b.fi, c.d+tag@mail.example.com", "[hidden], [hidden]"),
        ("Date 2026-11-19, 10 000 people", "Date 2026-11-19, 10 000 people"),
        ("Order 1234567 and 12345", "Order 1234567 and 12345"),
        ("line one\n0401234567\nline three", "line one\n[hidden]\nline three"),
        ("0401234567,0401234567", "[hidden],[hidden]"),
        ("no at sign example.org", "no at sign example.org"),
    ],
)
def test_mask_cases(text, expected):
    assert mask(text)[0] == expected


def test_display_id_is_short_and_stable():
    rid = UUID("11111111-2222-4333-8444-555555555555")
    assert display_id(rid) == display_id(rid) and re.fullmatch(r"R-[0-9A-F]{6}", display_id(rid))


def test_groups_cover_each_scale_once():
    assert GROUPS["nps"]["detractors"] == tuple(range(7))
    assert sorted(v for g in GROUPS["nps"].values() for v in g) == list(range(11))
    assert sorted(v for g in GROUPS["rating"].values() for v in g) == [1, 2, 3, 4, 5]
    assert GROUPS["thumbs"] == {"not-for-me": (0,), "good": (1,), "loved-it": (2,)}
