"""A partial fill of confirmed stock, completed from confirmed stock of the nearest kind (decision B56).

A request line that asks by product type or by words takes only the products its own search finds: milk for
coffee is a product type of its own and never fills a request for milk. When the confirmed stock of those
products falls short, the best confirmed option says how much is missing. This module finds what could fill the
rest from confirmed stock: one product outside the line's own candidates, judged by the ranking the by-product
substitutes use (`tta.offers.substitutes`) against the product the confirmed fill took first.

The product that completes a line is the first of that ranking that
- has confirmed stock and can be ordered: the allergen rule for substitutes holds, and so do the buyer's rules;
- rules out every allergen the buyer excludes: a product whose data leaves a doubt never comes in this way;
- carries every nutritional claim and certificate label the request line requires;
- keeps the formula where the formula matters (the request line or the buyer profile says so);
- with the line's confirmed stock covers the quantity asked; when none does, the buyer's minimum share of it.

The ranking shows a short list of the products Valio does not list (`tta.offers.substitutes.MAX_UNLISTED_SHOWN`).
A product that lacks a claim or a label the line requires could never complete it, so it is kept out of the
ranking (`skip`) and takes no place in that list: for lactose-free milk the regular milks of the category would
otherwise fill it. A product with confirmed stock can still be hidden behind ten whose quantity is not
confirmed; the line then gets no completion, which errs towards offering nothing.

Its line carries `SubstituteInfo` like any stand-in: it names what it replaces and what differs, and every rule
for a substitute judges it (F-05, F-08, F-11, F-12, P-05). `tta.offers.planning` puts the completed lines into a
draft of their own, and `tta.offers.options` lists that option after every other one. A line that named its
products by id is not completed here: it has its own stand-in (`tta.offers.stand_ins`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from decimal import Decimal

from tta.contracts.common import AvailabilityState
from tta.contracts.offer import OfferLine
from tta.contracts.ports import Catalog
from tta.contracts.product import Product
from tta.contracts.request import RequestLine
from tta.offers.combining import Fill
from tta.offers.deps import OfferDeps
from tta.offers.outcome import LineOutcome
from tta.offers.safety import ruled_out
from tta.offers.stand_ins import carries_required, line_from
from tta.offers.substitutes import Judged, rank_substitutes

ZERO = Decimal(0)


def completing_lines(
    outcomes: Sequence[LineOutcome], fills: Sequence[Fill], taken: Mapping[str, Decimal], minimum_fill: Decimal,
    deps: OfferDeps,
) -> tuple[OfferLine | None, ...]:
    """Per request line, the line that completes its confirmed fill, or None. `taken` is the confirmed stock
    already spoken for, in sales units per product: every confirmed fill and every stand-in. `minimum_fill` is
    the share of the quantity the buyer accepts (`BuyerProfile.min_fill_ratio`)."""
    lines: list[OfferLine | None] = []
    used = taken
    for outcome, picked in zip(outcomes, fills, strict=True):
        line = _completing_line(outcome, picked, used, minimum_fill, deps)
        if line is not None:
            used = {**used, line.product_id: used.get(line.product_id, ZERO) + line.quantity}
        lines.append(line)
    return tuple(lines)


def _completing_line(
    outcome: LineOutcome, picked: Fill, used: Mapping[str, Decimal], minimum_fill: Decimal, deps: OfferDeps
) -> OfferLine | None:
    need = outcome.need
    if outcome.asked.product_ids or not picked.picks or picked.missing <= 0 or need.quantity is None:
        return None  # named by id, nothing confirmed to complete, or nothing missing
    original = deps.catalog.get_product(picked.picks[0].product_id)
    if original is None:
        return None
    # Every product the line's own search found is left out: one that fits is in the fill or is the alternative
    # whose quantity is not confirmed, and one that dropped out has its reason in `excluded`.
    own = (*(each.product.id for each in outcome.fitting), *(each.product_id for each in outcome.excluded))
    skip = (*own, *_lacking_what_is_required(original, outcome.asked, deps.catalog))
    ranking = rank_substitutes(original, replace(need, quantity=picked.missing), deps, skip=skip)
    lines = [
        line for judged in ranking.ranked
        if _may_complete(judged, outcome) and (line := line_from(judged, ranking, used)) is not None
    ]
    whole = next((line for line in lines if line.covers >= picked.missing), None)
    if whole is not None:
        return whole
    least = minimum_fill * need.quantity - picked.covered
    if least <= 0:
        return None  # the confirmed stock alone reaches the buyer's minimum share: only the whole rest is worth it
    return next((line for line in lines if line.covers >= least), None)


def _lacking_what_is_required(original: Product, asked: RequestLine, catalog: Catalog) -> tuple[str, ...]:
    """The products the ranking would judge for `original` (those Valio lists for it, and its 5-digit category)
    that lack a nutritional claim or a certificate label the request line requires."""
    if not asked.required_claims and not asked.required_labels:
        return ()
    listed = (catalog.get_product(product_id) for product_id in catalog.listed_substitutes(original.id))
    pool = (*(product for product in listed if product is not None), *catalog.same_category(original.id, 5))
    return tuple(product.id for product in pool if not carries_required(product, asked))


def _may_complete(judged: Judged, outcome: LineOutcome) -> bool:
    candidate = judged.candidate
    return (
        judged.orderable
        and candidate.state is AvailabilityState.CONFIRMED
        and ruled_out(candidate.allergen_check)
        and carries_required(candidate.product, outcome.asked)
        and (judged.formula.keeps_formula or not outcome.need.formula_matters)
    )
