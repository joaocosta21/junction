"""One request line filled by several products: the option says when they differ in formula (P10 item F11)."""

from __future__ import annotations

from collections.abc import Sequence

from tta.availability.wording import format_amount
from tta.contracts.offer import OfferLine
from tta.contracts.ports import Catalog
from tta.contracts.product import FormulaCheck, FormulaOutcome
from tta.offers.formula import COMPONENTS_SAID, compare_formula
from tta.offers.wording import plain_name


def mixed_formulas(lines: Sequence[OfferLine], catalog: Catalog) -> str:
    """` B (id) differs in formula from A (id), which fills the same request line: fat 0 g, not 1.5 g.` One
    sentence per product that fills a request line next to another and does not keep its formula (P10 item
    F11); a difference of contents names the components before the figures (lane FC2). The first product of
    the line is the one measured against. A stand-in says its own formula (`SubstituteInfo.formula`), and a
    comparison the data cannot make says nothing here."""
    sentences = []
    for index in dict.fromkeys(line.request_line_index for line in lines):
        own = [line for line in lines if line.request_line_index == index and line.substitute is None]
        products = [catalog.get_product(line.product_id) for line in own]
        if len(own) < 2 or products[0] is None:
            continue
        for line, product in zip(own[1:], products[1:], strict=True):
            check = compare_formula(products[0], product) if product is not None else None
            if check is None or check.outcome is not FormulaOutcome.DIFFERENT:
                continue
            figures = [
                f"{each.nutrient.replace('_', ' ')} {format_amount(each.other)} g, not {format_amount(each.original)} g"
                for each in check.differences if not each.within_tolerance
            ]
            sentences.append(
                f" {_named(line)} differs in formula from {_named(own[0])}, which fills the same request "
                f"line: {_what_differs(check, figures)}."
            )
    return "".join(sentences)


def _what_differs(check: FormulaCheck, figures: Sequence[str]) -> str:
    """ "contains carrageenan and lacks lactase enzyme; fat 38 g, not 10 g": the components only one ingredient
    list names, in the labels' own words, before the figures. The fat source is said in our words only where
    the two lists could not be compared component by component."""
    contents = " and ".join(
        f"{verb} {_components(found)}"
        for verb, found in (("contains", check.only_in_other), ("lacks", check.only_in_original)) if found
    )
    by_words = "another fat source" if check.fat_source_differs and not check.contents_compared else ""
    said = "; ".join(part for part in (contents, ", ".join((*figures, *((by_words,) if by_words else ())))) if part)
    return said or "the data does not say in what"


def _components(found: Sequence[str]) -> str:
    said = ", ".join(plain_name(each) for each in found[:COMPONENTS_SAID])
    more = len(found) - COMPONENTS_SAID
    return f"{said} and {more} more" if more > 0 else said


def _named(line: OfferLine) -> str:
    return f"{plain_name(line.name)} ({line.product_id})"
