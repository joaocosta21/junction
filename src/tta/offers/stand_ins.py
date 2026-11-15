"""The SUBSTITUTE option's lines: a stand-in for a product named by id that confirmed stock does not supply in
full (SPEC section 5, step 3). The ranking itself is `tta.offers.substitutes`.

Which candidate of the ranking stands in (ours, decided on 14 Nov 2026):

1. Safe first (review P4, item M1): a candidate whose data rules out every excluded allergen.
2. Where the formula matters, because the request line says so (`RequestLine.keep_formula`, P10 item F5) or the
   buyer profile does for every line (`BuyerProfile.formula_matters`, decision B35): a candidate that
   keeps the formula. When none can be ordered the SUBSTITUTE option gets no stand-in for the line, the offer
   says so, and the formula-changing candidate is a labelled alternative that rule F-11 sends to a person.
3. Confirmed stock that replaces the original like for like (`ReplaceVerdict.REPLACEABLE`) before a product
   whose quantity Valio does not confirm. It fills the gap as far as its stock goes; the unconfirmed product
   that would fill the whole gap is then the labelled alternative.
4. Confirmed stock of the same kind (the same product type, use and flavour, and not a last resort) before a
   product whose quantity Valio does not confirm, even one Valio lists (lane FC2, 14 Nov 2026: a confirmed
   option comes first); stock that covers the whole gap before stock that covers part of it. The unconfirmed
   product the ranking puts before it, or the one that would fill the whole gap, is then the labelled
   alternative. Scenario 3 at the demo clock: 100 confirmed litres of another barista oat drink (475224)
   before 10 cases of Valio's listed 471690, whose quantity is not confirmed.
5. The ranking's own order.

A request in pieces is converted by content before anything is ranked (`Ranking.per_piece`; review P9b, item
Q14-1): 100 cartons of 1 L are 100 L, so 10 cases of 10 L stand in, not 100 cases.

What a stand-in gives up is said by `gives_up` as `tta.offers.substitutes` holds it, the function its list of
candidates uses: a stand-in's line and the list say the same words, whichever module words them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import ROUND_FLOOR, Decimal

from tta.contracts.common import QUANTITY_PLACES, AvailabilityState, round_money
from tta.contracts.offer import OfferLine, SubstituteInfo
from tta.contracts.product import PackSize, Product, ReplaceVerdict
from tta.contracts.request import RequestLine
from tta.offers.candidates import units_needed
from tta.offers.combining import Fill, floor_to_step, with_picks
from tta.offers.deps import OfferDeps
from tta.offers.lines import line_for
from tta.offers.outcome import LineOutcome
from tta.offers.safety import ruled_out
from tta.offers.substitute_wording import per_measure_difference
from tta.offers.substitutes import Judged, Ranking, gives_up, rank_substitutes
from tta.offers.wording import counted, line_label, measured, plain_name

ZERO = Decimal(0)
# What a line covers is stated to the places a quantity is written with (`tta.contracts.common`), rounded down:
# 31 packs of 0.7 kg for packs of 1.1 kg cover 19.727 of them, never 19.72727272727272727272727273 (review
# C3-F7), and never more than their content gives.
COVERS_STEP = Decimal(1).scaleb(-QUANTITY_PLACES)
WHOLE = Decimal(1)
NO_FORMULA_KEEPER = "no substitute that keeps the formula can be ordered"


@dataclass(frozen=True)
class StandIns:
    """What the stand-in search found, one entry per request line."""

    lines: tuple[OfferLine | None, ...]  # the stand-in of the SUBSTITUTE option
    # A second stand-in for the whole gap, never the suggestion: a product whose quantity is not confirmed where
    # confirmed stock fills only part of the gap, or a formula-changing one where the formula matters.
    alternatives: tuple[OfferLine | None, ...]
    # Per request line, for the option that offers only the named product: "" when there is nothing to say.
    said: tuple[str, ...]
    notes: tuple[str, ...]


@dataclass(frozen=True)
class _Found:
    line: OfferLine | None = None
    alternative: OfferLine | None = None
    said: str = ""
    notes: tuple[str, ...] = ()


def no_stand_ins(request_lines: int) -> StandIns:
    """What `substitute_lines` answers when no request line needs a stand-in."""
    nothing = (None,) * request_lines
    return StandIns(lines=nothing, alternatives=nothing, said=("",) * request_lines, notes=())


def substitute_lines(outcomes: Sequence[LineOutcome], fills: Sequence[Fill], deps: OfferDeps) -> StandIns:
    """One stand-in line per request line that needs one, in order. Stock is counted once: what the
    confirmed fills of the other lines take, and what the stand-ins of earlier lines took."""
    found: list[_Found] = []
    stood_in: Mapping[str, Decimal] = {}
    for index, (outcome, picked) in enumerate(zip(outcomes, fills, strict=True)):
        if not outcome.asked.product_ids or picked.missing <= 0:
            found.append(_Found())  # only when the request named products by id and they cannot be supplied in full
            continue
        used_elsewhere = _used_by([each for other, each in enumerate(fills) if other != index], stood_in)
        each = _substitute_line(outcome, picked, used_elsewhere, deps)
        for line in (each.line, each.alternative):
            if line is not None and line.availability.state is AvailabilityState.CONFIRMED:
                stood_in = {**stood_in, line.product_id: stood_in.get(line.product_id, ZERO) + line.quantity}
        found.append(each)
    return StandIns(
        lines=tuple(each.line for each in found),
        alternatives=tuple(each.alternative for each in found),
        said=tuple(each.said for each in found),
        notes=tuple(note for each in found for note in each.notes),
    )


def _used_by(fills: Sequence[Fill], stood_in: Mapping[str, Decimal]) -> Mapping[str, Decimal]:
    """Sales units per product that are already spoken for: `stood_in` plus the picks of `fills`."""
    used = stood_in
    for picked in fills:
        used = with_picks(used, picked)
    return used


def _substitute_line(
    outcome: LineOutcome, picked: Fill, used_elsewhere: Mapping[str, Decimal], deps: OfferDeps
) -> _Found:
    original = _original(outcome, picked, deps)
    # The substitute is asked to fill what the named products leave missing, not the whole line.
    gap = replace(outcome.need, quantity=picked.missing)
    ranking = rank_substitutes(original, gap, deps, skip=outcome.asked.product_ids)
    keep = outcome.need.formula_matters
    lines = [(judged, line_from(judged, ranking, used_elsewhere)) for judged in _in_order(outcome, ranking, keep)]
    orderable = [(judged, line) for judged, line in lines if line is not None]
    named = f"{plain_name(original.display_name)} ({original.id})"
    label = line_label(outcome.need.index)
    if not orderable:
        note = (
            f"{label}: no substitute for {named} passes the allergen rules, fits the "
            f"request and can be ordered; {counted(len(ranking.ranked), 'candidate')} ranked."
        )
        return _Found(notes=(note,))
    judged, line = orderable[0]
    if keep and not judged.formula.keeps_formula:
        # The formula matters and nothing that keeps it can be ordered: the formula-changing candidate is never
        # the stand-in of the SUBSTITUTE option. It is a labelled alternative, and rule F-11 sends it to a person.
        offered = (outcome.need.quantity or ZERO) - picked.missing
        rest = (
            f"{measured(offered, outcome.need.unit)} are offered and the rest is left for a person" if offered > 0
            else "the line is left for a person"
        )
        said = f"{NO_FORMULA_KEEPER}: {rest}"
        note = (
            f"{label}: {outcome.need.formula_said}, and {NO_FORMULA_KEEPER} for {named}. "
            f"{plain_name(line.name)} ({line.product_id}) does not keep it and is offered only as a labelled "
            "alternative for a person to decide."
        )
        return _Found(alternative=line, said=said[0].upper() + said[1:] + ".", notes=(note,))
    return _Found(line=line, alternative=_unconfirmed_for_the_rest(line, ranking, orderable, keep))


def _in_order(outcome: LineOutcome, ranking: Ranking, keep: bool) -> list[Judged]:
    """The candidates that fit the request line, in the order the module's docstring gives."""
    fitting = [judged for judged in ranking.ranked if carries_required(judged.candidate.product, outcome.asked)]
    return sorted(  # stable: within each group the ranking's own order holds
        fitting,
        key=lambda each: (
            not ruled_out(each.candidate.allergen_check),
            keep and not each.formula.keeps_formula,
            not _confirmed_like_for_like(each),
            _confirmed_same_kind(each, ranking),
        ),
    )


def carries_required(product: Product, asked: RequestLine) -> bool:
    """A stand-in must carry every nutritional claim and certificate label the request line requires (SPEC
    section 3, step 4; task SUST-1)."""
    required = frozenset(claim.strip().upper() for claim in asked.required_claims)
    labels = frozenset(label.strip().upper() for label in asked.required_labels)
    return required.issubset(product.nutritional_claims) and labels.issubset(product.labels)


def _confirmed_like_for_like(judged: Judged) -> bool:
    return (
        judged.candidate.state is AvailabilityState.CONFIRMED
        and judged.replaceable.verdict is ReplaceVerdict.REPLACEABLE
        and not judged.last_resort
    )


def _confirmed_same_kind(judged: Judged, ranking: Ranking) -> int:
    """0: confirmed stock of a product of the same type, use and flavour that covers all that is missing; 1:
    such stock that covers part of it; 2: anything else. Another brand, another formula or a claim that is
    not dietary do not keep it back; where the formula matters the group before this one already did."""
    candidate, gap, check = judged.candidate, ranking.need.quantity, judged.replaceable
    if candidate.state is not AvailabilityState.CONFIRMED or judged.last_resort or gap is None:
        return 2
    if check.other_type or check.other_use or check.other_flavour or check.plain_against_flavoured:
        return 2
    usable = candidate.assessment.usable_amount
    covers = usable is not None and candidate.per_unit is not None and usable * candidate.per_unit >= gap
    return 0 if covers else 1


def _unconfirmed_for_the_rest(
    line: OfferLine, ranking: Ranking, orderable: Sequence[tuple[Judged, OfferLine]], keep: bool
) -> OfferLine | None:
    """Confirmed stock stands in and leaves part of the gap open: the first product whose quantity Valio does
    not confirm, for the whole gap, as the labelled alternative. Confirmed stock that covers the gap and is
    not a like-for-like replacement: the unconfirmed product the ranking puts before it, if there is one.
    Under `keep` only one that keeps the formula."""
    gap = ranking.need.quantity
    if line.availability.state is not AvailabilityState.CONFIRMED or gap is None:
        return None
    unconfirmed = [
        (judged, other) for judged, other in orderable
        if judged.candidate.state is AvailabilityState.QUANTITY_NOT_CONFIRMED
        and (judged.formula.keeps_formula or not keep)
    ]
    if _content(line, ranking) < gap:
        return next((other for _, other in unconfirmed), None)
    place = {each.candidate.product.id: index for index, each in enumerate(ranking.ranked)}
    chosen = next(judged for judged, other in orderable if other is line)
    if chosen.replaceable.verdict is ReplaceVerdict.REPLACEABLE:
        return None
    return next(
        (
            other for judged, other in unconfirmed
            if place[judged.candidate.product.id] < place[chosen.candidate.product.id]
        ),
        None,
    )


def _content(line: OfferLine, ranking: Ranking) -> Decimal:
    """What the line covers in the unit the candidates were ranked in (litres or kilograms for pieces)."""
    return line.covers * (ranking.per_piece or Decimal(1))


def _original(outcome: LineOutcome, picked: Fill, deps: OfferDeps) -> Product:
    """The named product a substitute stands in for: the first one that confirmed stock does not supply."""
    supplied = {pick.product_id for pick in picked.picks}
    named = tuple(dict.fromkeys(outcome.asked.product_ids))
    product_id = next((each for each in named if each not in supplied), named[0])
    product = deps.catalog.get_product(product_id)
    if product is None:
        raise ValueError(f"named product {product_id} left the catalog while the offer was built")
    return product


def line_from(judged: Judged, ranking: Ranking, used_elsewhere: Mapping[str, Decimal]) -> OfferLine | None:
    """An offer line for the substitute, or `None` when it cannot be ordered for this line.

    Under confirmed-only a candidate with a claim that is not confirmed is not orderable: it was judged
    with the same need (`candidates.exclusion_for`), and `_confirmed_only` checks the finished lines again.
    """
    candidate, need = judged.candidate, ranking.need
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
        replaceable=judged.replaceable,
        original_net=original_net_of(_original_unit_price(ranking), ranking.original_pack, candidate.pack, units),
    )
    # `covers` is in the request's unit: content turned back into pieces where the request was in pieces.
    covers = min(units * candidate.per_unit, need.quantity) / (ranking.per_piece or Decimal(1))
    return line_for(candidate, ranking.asked, units, _stated(covers), now, info)


def _original_unit_price(ranking: Ranking) -> Decimal | None:
    """The price of one sales unit of the product asked for; None when it has no price that can be used now
    (`Ranking.original_price` is then None)."""
    price = ranking.original_price
    return price.catalog_price.value if price is not None and price.catalog_price is not None else None


def original_net_of(
    unit_price: Decimal | None, original: PackSize, other: PackSize, units: Decimal
) -> Decimal | None:
    """What the product asked for would have cost, before tax, for the content `units` sales units of the
    substitute hold: its price per litre or kilogram times that content (decision B60; rule P-05 reads it).

    Compared per litre or kilogram, as the trade-off sentence compares the two prices
    (`per_measure_difference`), so that a case is never compared with a carton. None when the product asked
    for has no usable price, or either pack size is not known, or the two are not in the same measure: not
    known, which the rule never reads as "not dearer".
    """
    if unit_price is None or per_measure_difference(unit_price, original, unit_price, other) is None:
        return None
    assert original.value and other.value  # noqa: S101 - `per_measure_difference` answered, so both are set
    return round_money(unit_price / original.value * other.value * units)


def _stated(covers: Decimal) -> Decimal:
    """`covers` as it is written: unchanged when `COVERS_STEP` holds it, else cut to it; and never with an
    exponent above zero. Content turned back into pieces is a division, and 25 / 0.5 answers `5E+1`: equal to
    50, and written `5E+1` by every reader that writes the Decimal as text."""
    cut = covers.quantize(COVERS_STEP, rounding=ROUND_FLOOR)
    stated = covers if cut == covers else cut
    return stated.quantize(WHOLE) if stated.as_tuple().exponent > 0 else stated
