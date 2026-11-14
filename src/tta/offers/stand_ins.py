"""The SUBSTITUTE option's lines: a stand-in for a product named by id that confirmed stock does not supply in
full (SPEC section 5, step 3). The ranking itself is `tta.offers.substitutes`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from decimal import Decimal

from tta.contracts.common import AvailabilityState
from tta.contracts.offer import OfferLine, SubstituteInfo
from tta.contracts.product import Product
from tta.offers.candidates import Need, units_needed
from tta.offers.combining import Fill, floor_to_step, with_picks
from tta.offers.deps import OfferDeps
from tta.offers.lines import line_for
from tta.offers.outcome import LineOutcome
from tta.offers.safety import ruled_out
from tta.offers.substitute_wording import gives_up
from tta.offers.substitutes import Judged, Ranking, rank_substitutes
from tta.offers.wording import counted, line_label, plain_name

ZERO = Decimal(0)


def substitute_lines(
    outcomes: Sequence[LineOutcome], fills: Sequence[Fill], deps: OfferDeps
) -> tuple[list[OfferLine | None], tuple[str, ...]]:
    """One stand-in line per request line that needs one, in order. Stock is counted once: what the
    confirmed fills of the other lines take, and what the stand-ins of earlier lines took."""
    lines: list[OfferLine | None] = []
    notes: list[str] = []
    stood_in: Mapping[str, Decimal] = {}
    for index, (outcome, picked) in enumerate(zip(outcomes, fills, strict=True)):
        if not outcome.asked.product_ids or picked.missing <= 0:
            lines.append(None)  # only when the request named products by id and they cannot be supplied in full
            continue
        used_elsewhere = _used_by([each for other, each in enumerate(fills) if other != index], stood_in)
        line, note = _substitute_line(outcome, picked, used_elsewhere, deps)
        if line is not None:
            stood_in = {**stood_in, line.product_id: stood_in.get(line.product_id, ZERO) + line.quantity}
        lines.append(line)
        notes.extend(note)
    return lines, tuple(notes)


def _used_by(fills: Sequence[Fill], stood_in: Mapping[str, Decimal]) -> Mapping[str, Decimal]:
    """Sales units per product that are already spoken for: `stood_in` plus the picks of `fills`."""
    used = stood_in
    for picked in fills:
        used = with_picks(used, picked)
    return used


def _substitute_line(
    outcome: LineOutcome, picked: Fill, used_elsewhere: Mapping[str, Decimal], deps: OfferDeps
) -> tuple[OfferLine | None, tuple[str, ...]]:
    original = _original(outcome, picked, deps)
    # The substitute is asked to fill what the named products leave missing, not the whole line.
    gap = replace(outcome.need, quantity=picked.missing)
    ranking = rank_substitutes(original, gap, deps, skip=outcome.asked.product_ids)
    required = frozenset(claim.strip().upper() for claim in outcome.asked.required_claims)
    labels = frozenset(label.strip().upper() for label in outcome.asked.required_labels)
    # Safe first (review P4, item M1): a candidate whose data rules out every excluded allergen comes before one
    # whose data leaves a doubt; within each group the ranking's own order holds (the sort is stable).
    for judged in sorted(ranking.ranked, key=lambda each: not ruled_out(each.candidate.allergen_check)):
        # A stand-in must carry every nutritional claim and certificate label the request line requires (SPEC
        # section 3, step 4; task SUST-1).
        product = judged.candidate.product
        if not required.issubset(product.nutritional_claims) or not labels.issubset(product.labels):
            continue
        line = _line_from(judged, gap, ranking, used_elsewhere)
        if line is not None:
            return line, ()
    named = f"{plain_name(original.display_name)} ({original.id})"
    note = (
        f"{line_label(outcome.need.index)}: no substitute for {named} passes the allergen rules, fits the "
        f"request and can be ordered; {counted(len(ranking.ranked), 'candidate')} ranked."
    )
    return None, (note,)


def _original(outcome: LineOutcome, picked: Fill, deps: OfferDeps) -> Product:
    """The named product a substitute stands in for: the first one that confirmed stock does not supply."""
    supplied = {pick.product_id for pick in picked.picks}
    named = tuple(dict.fromkeys(outcome.asked.product_ids))
    product_id = next((each for each in named if each not in supplied), named[0])
    product = deps.catalog.get_product(product_id)
    if product is None:
        raise ValueError(f"named product {product_id} left the catalog while the offer was built")
    return product


def _line_from(
    judged: Judged, need: Need, ranking: Ranking, used_elsewhere: Mapping[str, Decimal]
) -> OfferLine | None:
    """An offer line for the substitute, or `None` when it cannot be ordered for this line.

    Under confirmed-only a candidate with a claim that is not confirmed is not orderable: it was judged
    with the same need (`candidates.exclusion_for`), and `_confirmed_only` checks the finished lines again.
    """
    candidate = judged.candidate
    if not judged.orderable or need.quantity is None or candidate.per_unit is None:
        return None
    units = units_needed(candidate, need.quantity)
    if candidate.state is AvailabilityState.CONFIRMED:
        free = (candidate.assessment.usable_amount or ZERO) - used_elsewhere.get(candidate.product.id, ZERO)
        units = min(units, floor_to_step(free, candidate.lot_step))
    if units <= 0:
        return None
    now = ranking.lookup.now
    info = SubstituteInfo(
        original_id=ranking.original.id,
        original_name=ranking.original.display_name,
        listed_by_supplier=judged.listed,
        category_distance=judged.distance,
        allergen_check=judged.rule,
        claims_lost=judged.claims_lost,
        gives_up=gives_up(judged, ranking),
        formula=judged.formula,
        last_resort=judged.last_resort,
    )
    return line_for(candidate, need, units, min(units * candidate.per_unit, need.quantity), now, info)
