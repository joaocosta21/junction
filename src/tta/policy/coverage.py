"""What each request line of an option gets, in words, for rule P-03 (task FIX-12b).

The option carries one coverage entry per request line and a constraint check per thing each line asked for.
`option.fill_ratio` is the lowest line's ratio, and P-03 compares that; these readers say which line it is and
what every line gets, so a person never reads "only 0% is covered" for an option that covers a line in full.
A line is named by its product type, else its name terms, else the products it named, and always by its number.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal

from tta.contracts.common import ConstraintKind, Unit
from tta.contracts.offer import ConstraintCheck, Coverage, OfferOption
from tta.policy.text import format_number, format_ratio, join_words, plain_name

ONE_LINE = "the requested quantity"
# Rule P-03 for a request of several lines (the menu planner's order): a person reads how many items are covered
# in full and which are not, by name, never "0% of request line 2".
ITEMS_IN_FULL = "{full} of the {total} items asked for are covered in full"
NOTHING_OFFERED = "nothing is offered for {names}"
IN_PART = "{name} is covered in part ({amounts})"
ASKS_IN_FULL = "{buyer} asks for every item in full"
ASKS_AT_LEAST = "{buyer} asks for at least {minimum} of every item"
ONE_LINE_SAID = "only {fill} of {least} is covered, below the {minimum} minimum (covered: {covered})"
NO_BREAKDOWN = "only {fill} of {least} is covered, below the {minimum} minimum"
WHOLE = Decimal(1)
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


def line_names(option: OfferOption) -> dict[int, str]:
    """What each request line asked for, as a person says it: "sugar", "cocoa powder", "'almond'"; a line that
    names nothing a person would say is "request line 3"."""
    words = _line_words(option.constraint_checks)
    return {
        entry.request_line_index: words.get(entry.request_line_index) or _line_label(entry.request_line_index)
        for entry in option.coverage
    }


def lines_left_out(option: OfferOption) -> tuple[int, ...]:
    """The request lines the option offers nothing for: a coverage entry and no product, in the request's order."""
    offered = {line.request_line_index for line in option.lines}
    return tuple(sorted({entry.request_line_index for entry in option.coverage} - offered))


def coverage_said(option: OfferOption, minimum: Decimal, buyer: str) -> str:
    """Rule P-03's clause. One request line: `only 43.5% of the requested quantity is covered, below the 90%
    minimum (covered: 435 of 1,000 L)`. Several: `4 of the 7 items asked for are covered in full; nothing is
    offered for sugar, eggs and butter; Kallio Bakery asks for every item in full`."""
    covered = coverage_by_line(option)
    if covered is None:  # an option stored without its coverage per line: the share alone
        return NO_BREAKDOWN.format(
            fill=format_ratio(option.fill_ratio), least=least_covered(option), minimum=format_ratio(minimum)
        )
    if len(option.coverage) <= 1:
        return ONE_LINE_SAID.format(
            fill=format_ratio(option.fill_ratio), least=least_covered(option), minimum=format_ratio(minimum),
            covered=covered,
        )
    names = line_names(option)
    ordered = sorted(option.coverage, key=lambda entry: entry.request_line_index)
    full = [entry for entry in ordered if entry.fill_ratio >= WHOLE]
    empty = [names[entry.request_line_index] for entry in ordered if entry.covered <= 0]
    partial = [entry for entry in ordered if entry.covered > 0 and entry.fill_ratio < WHOLE]
    asks = ASKS_IN_FULL if minimum >= WHOLE else ASKS_AT_LEAST
    parts = (
        ITEMS_IN_FULL.format(full=len(full), total=len(ordered)),
        *((NOTHING_OFFERED.format(names=join_words(empty)),) if empty else ()),
        *(IN_PART.format(name=names[entry.request_line_index], amounts=_amounts(entry)) for entry in partial),
        asks.format(buyer=buyer, minimum=format_ratio(minimum)),
    )
    return "; ".join(parts)


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
        return _recipe_name(ids) or (f"product {ids[0]}" if len(ids) == 1 else f"products {join_words(ids)}")
    return ""


def _recipe_name(ids: Sequence[str]) -> str | None:
    """The recipe table's name for an ingredient a request line names by product ids (`cocoa_powder` -> "cocoa
    powder"): the key whose products hold every id of the line. None: no key of the table names them."""
    from tta.menus.recipes import shipped_recipes  # here: tta.menus is not needed to load the policy package

    wanted = set(ids)
    for key, products in shipped_recipes().named_products.items():
        if wanted <= set(products):
            return plain_name(key.replace("_", " "))
    return None
