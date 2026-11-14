"""What each request line of an option gets, in words, for rule P-03 (task FIX-12b).

The option carries one coverage entry per request line and a constraint check per thing each line asked for.
`option.fill_ratio` is the lowest line's ratio, and P-03 compares that; these readers say which line it is and
what every line gets, so a person never reads "only 0% is covered" for an option that covers a line in full.
A line is named by its product type, else its name terms, else the products it named, and always by its number.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from tta.contracts.common import ConstraintKind, Unit
from tta.contracts.offer import ConstraintCheck, Coverage, OfferOption
from tta.policy.text import format_number, join_words, plain_name

ONE_LINE = "the requested quantity"
UNIT_WORDS: Mapping[Unit, str] = {Unit.L: "L", Unit.KG: "kg", Unit.UNIT: "sales units"}
QUOTE = "'"


def least_covered(option: OfferOption) -> str:
    """`the requested quantity` for one request line; else `the quantity of request line 2`, the lowest line."""
    if len(option.coverage) <= 1:
        return ONE_LINE
    return f"the quantity of {_line_label(_least_first(option.coverage)[0].request_line_index)}"


def coverage_by_line(option: OfferOption) -> str | None:
    """`1,133 of 1,500 L` for one request line; for several, every line, the least covered first:
    `0 of 10 kg of butter, request line 2; 100 of 100 L of milk, request line 1`. `None`: no coverage."""
    if not option.coverage:
        return None
    if len(option.coverage) == 1:
        return _amounts(option.coverage[0])
    words = _line_words(option.constraint_checks)
    return "; ".join(_entry(entry, words.get(entry.request_line_index, "")) for entry in _least_first(option.coverage))


def _least_first(coverage: Sequence[Coverage]) -> list[Coverage]:
    return sorted(coverage, key=lambda entry: (entry.fill_ratio, entry.request_line_index))


def _line_label(index: int) -> str:
    return f"request line {index + 1}"


def _amounts(entry: Coverage) -> str:
    return f"{format_number(entry.covered)} of {format_number(entry.requested)} {UNIT_WORDS[entry.unit]}"


def _entry(entry: Coverage, words: str) -> str:
    named = f" of {words}" if words else ""
    return f"{_amounts(entry)}{named}, {_line_label(entry.request_line_index)}"


def _line_words(checks: Sequence[ConstraintCheck]) -> dict[int, str]:
    """What each request line asked for, from the subjects of its checks. Subjects are the buyer's own text
    (a name term) or codes, and read as data like a product name."""
    subjects: dict[int, dict[ConstraintKind, list[str]]] = {}
    for check in checks:
        if check.request_line_index is not None:
            kinds = subjects.setdefault(check.request_line_index, {})
            kinds.setdefault(check.kind, []).append(plain_name(check.subject))
    return {index: _words(kinds) for index, kinds in subjects.items()}


def _words(kinds: Mapping[ConstraintKind, list[str]]) -> str:
    if types := kinds.get(ConstraintKind.PRODUCT_TYPE):
        return types[0].replace("_", " ")
    if terms := kinds.get(ConstraintKind.NAME_TERM):
        return f"{QUOTE}{' '.join(terms)}{QUOTE}"
    if ids := kinds.get(ConstraintKind.PRODUCT_ID):
        return f"product {ids[0]}" if len(ids) == 1 else f"products {join_words(ids)}"
    return ""
