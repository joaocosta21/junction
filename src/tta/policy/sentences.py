"""From a template and facts to a sentence, and from a fact to the JSON value written in a decision.

A template comes from `rules.yaml`. Every placeholder is replaced in one pass, so text that came from
the data (a product name) is never read as a placeholder itself.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from tta.contracts.common import MONEY_PLACES, QUANTITY_PLACES, RATIO_PLACES
from tta.policy.facts import Missing, Reading
from tta.policy.rulebook import PLACEHOLDER, FactType
from tta.policy.text import format_datetime, format_limit, format_money, format_number, format_ratio

NOT_KNOWN = "not known"
NOT_LISTED = "not listed"
_NUMBER_FORMATS: dict[FactType, Callable[[Decimal], str]] = {
    FactType.MONEY: format_money,
    FactType.LIMIT: format_limit,
    FactType.RATIO: format_ratio,
    FactType.NUMBER: format_number,
}
# Decimal places of a number written to a decision, as the contracts serialise them (SPEC section 2).
_JSON_PLACES: dict[FactType, int] = {
    FactType.MONEY: MONEY_PLACES,
    FactType.LIMIT: MONEY_PLACES,
    FactType.RATIO: RATIO_PLACES,
    FactType.NUMBER: QUANTITY_PLACES,
}


def render(template: str, text_of: Callable[[str], str]) -> str:
    """Replace every {placeholder} with `text_of(name)`."""
    return PLACEHOLDER.sub(lambda match: text_of(match.group(1)), template)


def format_fact(value: Reading, fact_type: FactType) -> str:
    """A fact as it reads in a sentence."""
    if isinstance(value, Missing):
        return NOT_KNOWN
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, Decimal):
        return _NUMBER_FORMATS.get(fact_type, format_number)(value)
    if isinstance(value, datetime):
        return format_datetime(value)
    if isinstance(value, tuple):
        return ", ".join(value) if value else NOT_LISTED
    return value


def to_json(value: Reading, fact_type: FactType) -> Any:
    """A fact as a plain JSON value: numbers as numbers, a missing fact as null or as its known part."""
    if isinstance(value, Missing):
        return list(value.known) if value.known else None
    if isinstance(value, Decimal):
        quantum = Decimal(1).scaleb(-_JSON_PLACES.get(fact_type, QUANTITY_PLACES))
        return float(value.quantize(quantum, rounding=ROUND_HALF_UP))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple):
        return list(value)
    return value
