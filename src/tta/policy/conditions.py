"""Conditions in three-valued logic: true, false, or unknown because a fact is missing.

`all` is false as soon as one condition is false and `any` is true as soon as one is true, whatever
else is missing. Otherwise a missing fact leaves the group unknown, and the names of the facts that
left it so are reported: rule F-03 turns them into a decision for a human.
"""

from __future__ import annotations

import operator
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any

from tta.policy.facts import Missing, Reading
from tta.policy.rulebook import NUMBER_OPS, Condition, FactRef, Op, When
from tta.policy.text import unique


class Truth(Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Outcome:
    truth: Truth
    missing: tuple[str, ...] = ()  # the facts that left it unknown


Lookup = Callable[[str], Reading]

_TRUE = Outcome(Truth.TRUE)
_FALSE = Outcome(Truth.FALSE)
_ORDERINGS: Mapping[Op, Callable[[Decimal, Decimal], bool]] = {
    Op.GT: operator.gt, Op.GTE: operator.ge, Op.LT: operator.lt, Op.LTE: operator.le,
}


def evaluate(when: When, read: Lookup) -> Outcome:
    outcomes = [_node(node, read) for node in when.nodes]
    return _all(outcomes) if when.all_of else _any(outcomes)


def _node(node: Condition | When, read: Lookup) -> Outcome:
    return _condition(node, read) if isinstance(node, Condition) else evaluate(node, read)


def _all(outcomes: Sequence[Outcome]) -> Outcome:
    if any(outcome.truth is Truth.FALSE for outcome in outcomes):
        return _FALSE
    return _unknown_or(outcomes, _TRUE)


def _any(outcomes: Sequence[Outcome]) -> Outcome:
    if any(outcome.truth is Truth.TRUE for outcome in outcomes):
        return _TRUE
    return _unknown_or(outcomes, _FALSE)


def _unknown_or(outcomes: Sequence[Outcome], settled: Outcome) -> Outcome:
    missing = unique([name for outcome in outcomes for name in outcome.missing])
    return Outcome(Truth.UNKNOWN, missing) if missing else settled


def _condition(condition: Condition, read: Lookup) -> Outcome:
    left = read(condition.fact)
    other_fact = condition.value.fact if isinstance(condition.value, FactRef) else None
    right = read(other_fact) if other_fact is not None else condition.value
    if _known_part_matches(condition.op, left, right):
        return _TRUE
    sides = ((condition.fact, left), (other_fact, right))
    missing = tuple(name for name, value in sides if name is not None and isinstance(value, Missing))
    if missing:
        return Outcome(Truth.UNKNOWN, missing)
    return _TRUE if _holds(condition.op, left, right) else _FALSE


def _known_part_matches(op: Op, left: Any, right: Any) -> bool:
    """A partly known list settles `contains_any` when what is known already matches."""
    if op is not Op.CONTAINS_ANY or not isinstance(left, Missing) or isinstance(right, Missing):
        return False
    return any(item in left.known for item in right)


def _holds(op: Op, left: Any, right: Any) -> bool:
    if op in NUMBER_OPS:
        return _ORDERINGS[op](_number(left), _number(right))
    if op is Op.EQ:
        return _same(left, right)
    if op is Op.NE:
        return not _same(left, right)
    if op is Op.IN:
        return left in right
    if op is Op.NOT_IN:
        return left not in right
    if op is Op.CONTAINS_ANY:
        return any(item in left for item in right)
    if op is Op.IS_TRUE:
        return left is True
    if op is Op.IS_FALSE:
        return left is False
    return bool(left) if op is Op.NOT_EMPTY else not left  # the two ops left: not_empty, is_empty


def _is_number(value: Any) -> bool:
    return isinstance(value, Decimal | int | float) and not isinstance(value, bool)


def _number(value: Any) -> Decimal:
    """A number as Decimal. A float written in the rules file (0.9) is read as written, not as binary."""
    if not _is_number(value):
        raise TypeError(f"{value!r} is not a number")
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _same(left: Any, right: Any) -> bool:
    if _is_number(left) and _is_number(right):
        return _number(left) == _number(right)
    return left == right
