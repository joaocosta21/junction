"""Conditions use three-valued logic: a missing fact leaves a rule unknown unless another fact settles it."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from tta.policy.conditions import Truth, evaluate
from tta.policy.facts import Missing
from tta.policy.rulebook import When

GONE = Missing("not given")


def _evaluate(when: dict[str, Any], facts: dict[str, Any]) -> tuple[Truth, tuple[str, ...]]:
    outcome = evaluate(When.model_validate(when), facts.__getitem__)
    return outcome.truth, outcome.missing


@pytest.mark.parametrize(
    ("op", "left", "value", "expected"),
    [
        ("eq", "STRICT", "STRICT", True), ("eq", "STRICT", "DECLARED_ONLY", False),
        ("ne", "STRICT", "DECLARED_ONLY", True), ("ne", "STRICT", "STRICT", False),
        ("gt", Decimal("750.01"), 750, True), ("gt", Decimal("750.00"), 750, False),
        ("gte", Decimal("750.00"), 750, True), ("gte", Decimal("749.99"), 750, False),
        ("lt", Decimal("0.749"), 0.9, True), ("lt", Decimal("0.9"), 0.9, False),
        ("lte", Decimal("0.9"), 0.9, True), ("lte", Decimal("0.91"), 0.9, False),
        ("in", "OUTSIDE", ["LISTED_BY_SUPPLIER", "SAME_CATEGORY"], False),
        ("in", "SAME_CATEGORY", ["LISTED_BY_SUPPLIER", "SAME_CATEGORY"], True),
        ("not_in", "OUTSIDE", ["LISTED_BY_SUPPLIER"], True), ("not_in", "OUTSIDE", [], True),
        ("contains_any", ("PASS", "REJECT"), ["REJECT"], True), ("contains_any", ("PASS",), ["REJECT"], False),
        ("contains_any", (), ["REJECT"], False),
    ],
)
def test_operators_with_a_value(op: str, left: Any, value: Any, expected: bool) -> None:
    truth, missing = _evaluate({"all": [{"fact": "x.y", "op": op, "value": value}]}, {"x.y": left})

    assert truth is (Truth.TRUE if expected else Truth.FALSE) and missing == ()


@pytest.mark.parametrize(
    ("op", "left", "expected"),
    [
        ("is_true", True, True), ("is_true", False, False), ("is_false", False, True), ("is_false", True, False),
        ("not_empty", ("AM",), True), ("not_empty", (), False), ("is_empty", (), True), ("is_empty", ("AM",), False),
    ],
)
def test_operators_without_a_value(op: str, left: Any, expected: bool) -> None:
    truth, _ = _evaluate({"all": [{"fact": "x.y", "op": op}]}, {"x.y": left})

    assert truth is (Truth.TRUE if expected else Truth.FALSE)


def test_a_value_can_be_another_fact() -> None:
    when = {"all": [{"fact": "option.net", "op": "gt", "value": {"fact": "profile.limit"}}]}

    assert _evaluate(when, {"option.net": Decimal(900), "profile.limit": Decimal(750)})[0] is Truth.TRUE
    assert _evaluate(when, {"option.net": Decimal(900), "profile.limit": GONE}) == (Truth.UNKNOWN, ("profile.limit",))


def test_a_missing_fact_leaves_a_condition_unknown_and_is_named() -> None:
    truth, missing = _evaluate({"all": [{"fact": "x.y", "op": "is_true"}]}, {"x.y": GONE})

    assert truth is Truth.UNKNOWN and missing == ("x.y",)


def test_all_is_false_as_soon_as_one_condition_is_false_whatever_is_missing() -> None:
    when = {"all": [{"fact": "a.a", "op": "is_true"}, {"fact": "b.b", "op": "is_true"}]}

    assert _evaluate(when, {"a.a": False, "b.b": GONE}) == (Truth.FALSE, ())
    assert _evaluate(when, {"a.a": GONE, "b.b": False}) == (Truth.FALSE, ())
    assert _evaluate(when, {"a.a": True, "b.b": GONE}) == (Truth.UNKNOWN, ("b.b",))
    assert _evaluate(when, {"a.a": True, "b.b": True}) == (Truth.TRUE, ())


def test_any_is_true_as_soon_as_one_condition_is_true_whatever_is_missing() -> None:
    when = {"any": [{"fact": "a.a", "op": "is_true"}, {"fact": "b.b", "op": "is_true"}]}

    assert _evaluate(when, {"a.a": True, "b.b": GONE}) == (Truth.TRUE, ())
    assert _evaluate(when, {"a.a": False, "b.b": GONE}) == (Truth.UNKNOWN, ("b.b",))
    assert _evaluate(when, {"a.a": False, "b.b": False}) == (Truth.FALSE, ())
    assert _evaluate(when, {"a.a": GONE, "b.b": GONE}) == (Truth.UNKNOWN, ("a.a", "b.b"))


def test_groups_nest() -> None:
    when = {"all": [
        {"fact": "a.a", "op": "is_true"},
        {"any": [{"fact": "b.b", "op": "is_true"}, {"fact": "c.c", "op": "is_false"}]},
    ]}

    assert _evaluate(when, {"a.a": True, "b.b": False, "c.c": False})[0] is Truth.TRUE
    assert _evaluate(when, {"a.a": True, "b.b": False, "c.c": True})[0] is Truth.FALSE
    assert _evaluate(when, {"a.a": False, "b.b": GONE, "c.c": GONE}) == (Truth.FALSE, ())
    assert _evaluate(when, {"a.a": True, "b.b": GONE, "c.c": True}) == (Truth.UNKNOWN, ("b.b",))


def test_a_partly_known_list_settles_a_condition_only_when_what_is_known_matches() -> None:
    partial = Missing("the check does not cover AW", known=("REJECT",))
    when = {"all": [{"fact": "x.y", "op": "contains_any", "value": ["REJECT"]}]}
    other = {"all": [{"fact": "x.y", "op": "contains_any", "value": ["TO_HUMAN"]}]}

    assert _evaluate(when, {"x.y": partial}) == (Truth.TRUE, ())
    assert _evaluate(other, {"x.y": partial}) == (Truth.UNKNOWN, ("x.y",))


def test_a_group_holds_either_all_or_any() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        When.model_validate({"all": [{"fact": "a.a", "op": "is_true"}], "any": [{"fact": "b.b", "op": "is_true"}]})
    with pytest.raises(ValueError, match="exactly one"):
        When.model_validate({})
