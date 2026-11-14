"""The two catalog kinds for the product an offer chose: the cheaper product with the same formula and the
larger pack (P10 F6, P15 R5), built from the catalog and one look at price and stock.

For each request line the first option covers with one product that is no substitute: the other products of its
type are judged from the product file first, with the offer package's own functions (read-only): the formula
measure `compare_formula`, the dietary claims lost `claims_lost`, and `replace_check` (same type, same flavour,
same use). Only a like-for-like product that keeps the formula goes on; price and stock are asked for those alone.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass

from tta.catalog.kinds import product_types_of
from tta.contracts.offer import Offer, OfferLine
from tta.contracts.policy import BuyerProfile
from tta.contracts.ports import Catalog
from tta.contracts.product import FormulaCheck, FormulaOutcome, Product, ReplaceVerdict
from tta.contracts.request import ProductQuery, PurchaseRequest, RequestLine
from tta.contracts.suggestion import Suggestion
from tta.offers.candidates import evaluate, need_for, price_problem
from tta.offers.deps import Lookup
from tta.offers.formula import compare_formula
from tta.offers.substitutes import claims_lost, replace_check
from tta.suggestions.cheaper import CheaperOption, cheaper_same_formula
from tta.suggestions.packs import MEASURES, PackOption, larger_pack
from tta.suggestions.thresholds import ALTERNATIVES_MAX_POOL

LookUp = Callable[[Iterable[str]], Lookup]


@dataclass(frozen=True)
class Offered:
    """A request line the first option covers with one product, which stands in for nothing."""

    line_index: int
    product: Product


def offered_products(request: PurchaseRequest, offer: Offer, catalog: Catalog) -> tuple[Offered, ...]:
    """One per request line that the first option covers with exactly one product of the catalog."""
    if not offer.options:
        return ()
    by_line: dict[int, list[OfferLine]] = {}
    for line in offer.options[0].lines:
        by_line.setdefault(line.request_line_index, []).append(line)
    found = []
    for index, lines in sorted(by_line.items()):
        if len(lines) != 1 or lines[0].substitute is not None or index >= len(request.lines):
            continue
        product = catalog.get_product(lines[0].product_id)
        if product is not None and not product.deleted:
            found.append(Offered(line_index=index, product=product))
    return tuple(found)


def alternatives(customer_id: str, request: PurchaseRequest, offered: Sequence[Offered], profile: BuyerProfile,
                 catalog: Catalog, look_up: LookUp) -> tuple[Suggestion, ...]:
    """For each offered product: the cheaper product with the same formula, then the larger pack, where one
    exists. Where the profile says the formula matters, a cheaper product of another brand stays silent."""
    return tuple(_for_lines(customer_id, request, offered, profile, catalog, look_up))


def _for_lines(customer_id: str, request: PurchaseRequest, offered: Sequence[Offered], profile: BuyerProfile,
               catalog: Catalog, look_up: LookUp) -> Iterator[Suggestion]:
    for each in offered:
        keepers = _formula_keepers(each.product, request.lines[each.line_index], catalog)
        if not keepers:
            continue
        lookup = look_up([each.product.id, *(product.id for product, _ in keepers)])
        original = _pack(each.product, each.line_index, request, profile, catalog, lookup, None)
        if original is None:
            continue
        options = [
            CheaperOption(pack=pack, formula=formula) for product, formula in keepers
            if (pack := _pack(product, each.line_index, request, profile, catalog, lookup, original, formula)
                ) is not None
        ]
        cheaper = cheaper_same_formula(customer_id, request, each.line_index, original, options,
                                       same_brand_only=profile.formula_matters)
        if cheaper is not None:
            yield cheaper
        larger = larger_pack(customer_id, request, each.line_index, original, [option.pack for option in options])
        if larger is not None:
            yield larger


def _formula_keepers(original: Product, line: RequestLine, catalog: Catalog) -> list[tuple[Product, FormulaCheck]]:
    """The products of the original's type that can take its place like for like and keep its formula, judged
    from the product file alone."""
    keepers: list[tuple[Product, FormulaCheck]] = []
    for other in _same_type(original, line, catalog):
        formula = compare_formula(original, other)
        if not formula.keeps_formula:
            continue
        judged = replace_check(original, other, formula, claims_lost(original, other))
        if judged.verdict is ReplaceVerdict.REPLACEABLE:
            keepers.append((other, formula))
    return keepers


def _same_type(original: Product, line: RequestLine, catalog: Catalog) -> list[Product]:
    """Every other product of the original's product types (the line's own type first), each once, at most
    `ALTERNATIVES_MAX_POOL` per type. A product of no type of ours has no pool."""
    types = dict.fromkeys([*([line.product_type] if line.product_type else []), *product_types_of(original)])
    found: dict[str, Product] = {}
    for key in types:
        # Raises `InvalidRequest` for a type the table does not hold. None can arrive here: the line's type was
        # checked when the offer was built and the product's own types are keys of the table. It is not caught:
        # a silent "no alternative" would hide a broken table (review finding S15).
        result = catalog.search(ProductQuery(product_type=key, limit=ALTERNATIVES_MAX_POOL))
        for product in result.products:
            if product.id != original.id and not product.deleted:
                found.setdefault(product.id, product)
    return list(found.values())


def _pack(product: Product, line_index: int, request: PurchaseRequest, profile: BuyerProfile, catalog: Catalog,
          lookup: Lookup, original: PackOption | None, formula: FormulaCheck | None = None) -> PackOption | None:
    """The product's pack in litres or kilograms with its price and availability, read as an offer line reads
    them; None when the size or the price is not known. `original`: the pack it is measured against, with the
    `formula` found against it.

    Nothing here judges allergens, claims or stock: every suggestion built from a pack goes through the guard
    (`tta.suggestions.guard.check`), which drops a product whose data does not rule out an excluded allergen
    by the offer's own test, `tta.offers.safety.ruled_out` (Python review, items P3 and P10)."""
    line = request.lines[line_index]
    units = (original.measure,) if original is not None else (line.unit,) if line.unit in MEASURES else MEASURES
    for unit in units:
        measured = line.model_copy(update={"unit": unit})
        candidate = evaluate(product, need_for(line_index, measured, request, profile), lookup, catalog)
        if candidate.per_unit is None or price_problem(candidate.price, lookup.now) is not None:
            continue
        return PackOption(
            product_id=product.id, name=product.display_name, pack_size=candidate.per_unit, measure=unit,
            unit_net_price_eur=candidate.unit_price, availability=candidate.assessment,
            lot_step=candidate.lot_step,
            same_product=formula is not None and formula.outcome is FormulaOutcome.SAME_PRODUCT_OTHER_PACK,
        )
    return None
