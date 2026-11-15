"""Which lines go into which option (SPEC section 5, step 3).

BEST_CONFIRMED uses confirmed stock only, ranked by the buyer's preference and then price (task SUST-1).
CHEAPEST_CONFIRMED is the price fill of the same stock, when a preference other than price chose another one.
ALTERNATIVE_UNCONFIRMED is the fitting product whose quantity Valio does not confirm with the lowest total for
the quantity asked. SUBSTITUTE keeps the confirmed stock of a product named by id and fills what is missing
with the best substitute. A line asked for by type or by words whose confirmed stock falls short gets one more
draft: the same confirmed stock, completed from confirmed stock of the nearest kind (`tta.offers.completing`).

Safe first (review P4, item M1): with an allergen excluded, the three kinds above take only products whose data
rules it out. Confirmed stock whose data leaves a doubt goes into a second ALTERNATIVE_UNCONFIRMED draft, the
price fill of all confirmed stock, which `tta.offers.options` titles "Alternative: allergen not ruled out".

A variant nobody asked for comes last (`tta.offers.variants`): regular milk before lactose-free milk.

An unconfirmed product is no alternative when it costs no less than confirmed stock that covers the whole
quantity (review P2, item W4): it would give the person who decides nothing.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from tta.contracts.common import AvailabilityState, ExclusionReason, OptionKind, Preference
from tta.contracts.offer import OfferLine
from tta.contracts.request import RequestLine
from tta.offers.candidates import Candidate, units_needed
from tta.offers.combining import Fill, Supply, fill, with_picks
from tta.offers.completing import completing_lines
from tta.offers.deps import OfferDeps
from tta.offers.lines import line_for
from tta.offers.options import Draft
from tta.offers.outcome import LineOutcome
from tta.offers.preference import tiers
from tta.offers.safety import open_allergens, ruled_out, who_decides
from tta.offers.stand_ins import StandIns, no_stand_ins, substitute_lines
from tta.offers.variants import variant_word
from tta.offers.wording import counted, eur, for_line, line_label, line_names, listed

ZERO = Decimal(0)
WHOLE = Decimal(1)
CONFIRMED_ONLY = "confirmed data only was asked for"
# What the note says of the products that dropped out for a reason that exists only under confirmed-only.
LEFT_OUT_UNDER_CONFIRMED_ONLY = {
    ExclusionReason.QUANTITY_NOT_CONFIRMED: "whose quantity Valio does not confirm",
    ExclusionReason.DELIVERY_DATE_NOT_CONFIRMED: "whose delivery date Valio's data does not confirm",
}


@dataclass(frozen=True)
class Plan:
    drafts: tuple[Draft, ...]
    notes: tuple[str, ...]


@dataclass(frozen=True)
class _Pools:
    safe: tuple[Candidate, ...]  # confirmed stock whose data rules out every excluded allergen
    doubtful: tuple[Candidate, ...]  # confirmed stock whose data leaves an excluded allergen open
    unconfirmed: tuple[Candidate, ...]
    notes: tuple[str, ...]

    @property
    def confirmed(self) -> tuple[Candidate, ...]:
        return (*self.safe, *self.doubtful)


def plan_options(
    outcomes: Sequence[LineOutcome], now: datetime, deps: OfferDeps, prefer: Preference = Preference.PRICE, *,
    minimum_fill: Decimal = WHOLE, stand_in: bool = True,
) -> Plan:
    """`minimum_fill`: the share of a quantity the buyer accepts, for the draft that completes a partial fill.
    `stand_in=False` leaves out everything that asks for substitutes: the stand-ins of products named by id and
    the completed draft (`tta.offers.later` plans a later date from the request's own products only)."""
    pools = [_pools(outcome) for outcome in outcomes]
    fills = _confirmed_fills(outcomes, pools, prefer)
    confirmed = _all_confirmed_lines(outcomes, pools, fills, now)
    by_price = fills if prefer is Preference.PRICE else _confirmed_fills(outcomes, pools, Preference.PRICE)
    cheapest = confirmed if prefer is Preference.PRICE else _all_confirmed_lines(outcomes, pools, by_price, now)
    alternatives, dear_notes = _unconfirmed_lines(outcomes, pools, cheapest, now)
    stand_ins = substitute_lines(outcomes, fills, deps) if stand_in else no_stand_ins(len(outcomes))
    substitutes, substitute_notes = stand_ins.lines, stand_ins.notes
    drafts = [Draft(OptionKind.BEST_CONFIRMED, _flatten(confirmed), said=_said(outcomes, stand_ins.said))]
    if [each.picks for each in by_price] != [each.picks for each in fills]:
        # Whether the price fill is also cheaper is judged on the totals (`tta.offers.options`).
        drafts.append(Draft(OptionKind.CHEAPEST_CONFIRMED, _flatten(cheapest)))
    drafts.extend(_doubtful(outcomes, pools, prefer, now))
    if any(alternatives):
        drafts.append(Draft(OptionKind.ALTERNATIVE_UNCONFIRMED, _swapped(confirmed, alternatives)))
    if any(substitutes):
        drafts.append(Draft(_stand_in_kind(substitutes), _extended(confirmed, substitutes)))
    drafts.extend(_labelled_stand_ins(confirmed, stand_ins))
    if stand_in:
        drafts.extend(_completed(outcomes, fills, confirmed, stand_ins, minimum_fill, deps))
    kept, filter_notes = _confirmed_only(outcomes, [draft for draft in drafts if draft.lines])
    notes = [note for pool in pools for note in pool.notes]
    safety_notes = _no_safe_notes(outcomes, pools, substitutes)
    return Plan(drafts=tuple(kept), notes=(*notes, *safety_notes, *dear_notes, *substitute_notes, *filter_notes))


def _completed(
    outcomes: Sequence[LineOutcome], fills: Sequence[Fill], confirmed: Sequence[tuple[OfferLine, ...]],
    stand_ins: StandIns, minimum_fill: Decimal, deps: OfferDeps,
) -> tuple[Draft, ...]:
    """The draft that holds the confirmed fill of every line and, where that falls short on a line asked for by
    type or by words, the confirmed product of the nearest kind that completes it (`tta.offers.completing`)."""
    lines = completing_lines(outcomes, fills, _taken(fills, stand_ins), minimum_fill, deps)
    if not any(lines):
        return ()
    return (Draft(OptionKind.SUBSTITUTE, _extended(confirmed, lines), completed=True),)


def _taken(fills: Sequence[Fill], stand_ins: StandIns) -> Mapping[str, Decimal]:
    """Confirmed stock already spoken for, in sales units per product: every confirmed fill, and every stand-in
    of a product named by id."""
    used: Mapping[str, Decimal] = {}
    for picked in fills:
        used = with_picks(used, picked)
    for line in (*stand_ins.lines, *stand_ins.alternatives):
        if line is not None and line.availability.state is AvailabilityState.CONFIRMED:
            used = {**used, line.product_id: used.get(line.product_id, ZERO) + line.quantity}
    return used


def _labelled_stand_ins(confirmed: Sequence[tuple[OfferLine, ...]], stand_ins: StandIns) -> tuple[Draft, ...]:
    """The option with the second stand-ins (`StandIns.alternatives`): a product whose quantity is not confirmed
    for the whole gap, or a formula-changing one where the formula matters. A request line that has none keeps
    its own stand-in. `tta.offers.options` labels the option and never ranks it first among its like."""
    if not any(stand_ins.alternatives):
        return ()
    lines = [other or own for own, other in zip(stand_ins.lines, stand_ins.alternatives, strict=True)]
    return (Draft(_stand_in_kind(lines), _extended(confirmed, lines)),)


def _stand_in_kind(stand_ins: Sequence[OfferLine | None]) -> OptionKind:
    """An option that holds any quantity Valio does not confirm is an alternative: it is titled and summarised
    as one and ranks after every option of confirmed stock only (Python review, item P2). Before, a stand-in
    whose quantity was not confirmed made an option of kind SUBSTITUTE that read as a confirmed full fill."""
    unconfirmed = any(
        line is not None and line.availability.state is not AvailabilityState.CONFIRMED for line in stand_ins
    )
    return OptionKind.ALTERNATIVE_UNCONFIRMED if unconfirmed else OptionKind.SUBSTITUTE


def _said(outcomes: Sequence[LineOutcome], said: Sequence[str]) -> str:
    """What the stand-in search has to say on the option that offers only the named products. It is part of
    the option's summary, which a person reads: with several lines each sentence names its line by the line's
    own words, never by its number."""
    several = len(outcomes) > 1
    names = line_names(tuple(outcome.asked for outcome in outcomes))
    return "".join(
        f" {for_line(name)}: {each[0].lower()}{each[1:]}" if several else f" {each}"
        for name, each in zip(names, said, strict=True) if each
    )


def _confirmed_only(outcomes: Sequence[LineOutcome], drafts: Sequence[Draft]) -> tuple[list[Draft], tuple[str, ...]]:
    """Under confirmed-only, keep only options whose every line is confirmed for order (SPEC section 4)."""
    if not any(outcome.need.require_confirmed for outcome in outcomes):
        return list(drafts), ()
    dated = any(outcome.need.dated for outcome in outcomes)
    kept = [draft for draft in drafts if all(line.confirmed_for_order(dated=dated) for line in draft.lines)]
    if len(kept) == len(drafts):
        return kept, ()
    left_out = counted(len(drafts) - len(kept), "option")
    return kept, (f"{left_out} left out because a claim an order depends on is not confirmed, and {CONFIRMED_ONLY}.",)


def _pools(outcome: LineOutcome) -> _Pools:
    """The confirmed and the unconfirmed candidates of a line.

    Under confirmed-only every fitting candidate is confirmed for order: the others dropped out with a
    reason (`candidates.exclusion_for`), so the unconfirmed pool is empty and the notes say how many went.
    """
    confirmed = tuple(each for each in outcome.fitting if each.state is AvailabilityState.CONFIRMED)
    unconfirmed = tuple(each for each in outcome.fitting if each.state is AvailabilityState.QUANTITY_NOT_CONFIRMED)
    return _Pools(
        safe=tuple(each for each in confirmed if ruled_out(each.allergen_check)),
        doubtful=tuple(each for each in confirmed if not ruled_out(each.allergen_check)),
        unconfirmed=unconfirmed,
        notes=_confirmed_only_notes(outcome),
    )


def _no_safe_notes(
    outcomes: Sequence[LineOutcome], pools: Sequence[_Pools], substitutes: Sequence[OfferLine | None]
) -> tuple[str, ...]:
    """A line where no product that could be offered rules the excluded allergen out: nothing is suggested as
    safe, and the offer says so (review P4, rule R3)."""
    notes = []
    for outcome, pool, stand_in in zip(outcomes, pools, substitutes, strict=True):
        fitting = (*pool.confirmed, *pool.unconfirmed)
        doubtful = [each for each in fitting if not ruled_out(each.allergen_check)]
        if not doubtful or len(doubtful) < len(fitting):
            continue  # nothing is in doubt, or a product that rules the allergen out can be offered
        if stand_in is not None and ruled_out(stand_in.allergen_check):
            continue  # a substitute whose data rules the allergen out is offered in place of the named product
        allergens = open_allergens(each.allergen_check for each in doubtful)
        notes.append(
            f"{line_label(outcome.need.index)}: no product whose data rules out {allergens} can be offered, so no "
            f"option is suggested as safe: {who_decides(each.allergen_check for each in doubtful)} on each "
            "alternative."
        )
    return tuple(notes)


def _doubtful(
    outcomes: Sequence[LineOutcome], pools: Sequence[_Pools], prefer: Preference, now: datetime
) -> tuple[Draft, ...]:
    """The fill of all confirmed stock, when it takes a product whose data does not rule an excluded allergen
    out. It is never the suggestion (`tta.offers.options` ranks it after every safe option)."""
    if not any(pool.doubtful for pool in pools):
        return ()
    fills = _confirmed_fills(outcomes, pools, prefer, with_doubtful=True)
    doubtful = {each.product.id for pool in pools for each in pool.doubtful}
    if not any(pick.product_id in doubtful for picked in fills for pick in picked.picks):
        return ()
    lines = _all_confirmed_lines(outcomes, pools, fills, now)
    return (Draft(OptionKind.ALTERNATIVE_UNCONFIRMED, _flatten(lines)),)


def _confirmed_only_notes(outcome: LineOutcome) -> tuple[str, ...]:
    """One note per reason that exists only under confirmed-only; each product is also in `excluded`."""
    notes = []
    for reason, what in LEFT_OUT_UNDER_CONFIRMED_ONLY.items():
        ids = [exclusion.product_id for exclusion in outcome.excluded if exclusion.reason is reason]
        if not ids:
            continue
        verb = "was" if len(ids) == 1 else "were"
        notes.append(
            f"{line_label(outcome.need.index)}: {counted(len(ids), 'product')} {what} {verb} left out, "
            f"because {CONFIRMED_ONLY}: {listed(ids)}."
        )
    return tuple(notes)


def _all_confirmed_lines(
    outcomes: Sequence[LineOutcome], pools: Sequence[_Pools], fills: Sequence[Fill], now: datetime
) -> list[tuple[OfferLine, ...]]:
    return [
        _confirmed_lines(outcome, pool, picked, now)
        for outcome, pool, picked in zip(outcomes, pools, fills, strict=True)
    ]


def _supply(candidate: Candidate, already_used: Decimal, tier: int) -> Supply:
    if candidate.per_unit is None or candidate.assessment.usable_amount is None:
        raise ValueError(f"product {candidate.product.id} is not confirmed stock with a known pack size")
    return Supply(
        product_id=candidate.product.id,
        per_unit=candidate.per_unit,
        unit_price=candidate.unit_price,
        # `usable_amount` is set only for state CONFIRMED: a placeholder amount never becomes a supply.
        usable=candidate.assessment.usable_amount - already_used,
        lot_step=candidate.lot_step,
        tier=tier,
    )


def _confirmed_fills(
    outcomes: Sequence[LineOutcome], pools: Sequence[_Pools], prefer: Preference, *, with_doubtful: bool = False
) -> list[Fill]:
    """One fill per request line, in order. Stock one line takes is not offered to the next.

    Only products whose data rules out every excluded allergen, unless `with_doubtful` (review P4, item M1).
    """
    used: Mapping[str, Decimal] = {}
    fills: list[Fill] = []
    for outcome, pool in zip(outcomes, pools, strict=True):
        stock = pool.confirmed if with_doubtful else pool.safe
        picked = _regular_first(outcome, stock, prefer, used)
        used = with_picks(used, picked)
        fills.append(picked)
    return fills


def _regular_first(
    outcome: LineOutcome, stock: Sequence[Candidate], prefer: Preference, used: Mapping[str, Decimal]
) -> Fill:
    """The fill of the regular products; a variant nobody asked for fills only what they leave missing:
    lactose-free milk answers a request for milk only where regular milk cannot (`tta.offers.variants`)."""
    requested = outcome.need.quantity or ZERO
    regular = [each for each in stock if not _is_variant(outcome.asked, each)]
    variants = [each for each in stock if _is_variant(outcome.asked, each)]
    picked = fill(requested, _supplies(regular, prefer, used))
    if picked.missing <= 0 or not variants:
        return picked
    rest = fill(picked.missing, _supplies(variants, prefer, used))
    return Fill(requested, (*picked.picks, *rest.picks))


def _supplies(stock: Sequence[Candidate], prefer: Preference, used: Mapping[str, Decimal]) -> list[Supply]:
    tier = tiers(stock, prefer)
    return [_supply(each, used.get(each.product.id, ZERO), tier[each.product.id]) for each in stock]


def _is_variant(asked: RequestLine, candidate: Candidate) -> bool:
    return variant_word(asked, candidate.product.nutritional_claims) is not None


def _confirmed_lines(outcome: LineOutcome, pool: _Pools, picked: Fill, now: datetime) -> tuple[OfferLine, ...]:
    by_id = {each.product.id: each for each in pool.confirmed}
    return tuple(line_for(by_id[pick.product_id], outcome.need, pick.units, pick.covers, now) for pick in picked.picks)


def _unconfirmed_lines(
    outcomes: Sequence[LineOutcome], pools: Sequence[_Pools], cheapest: Sequence[tuple[OfferLine, ...]],
    now: datetime,
) -> tuple[list[OfferLine | None], tuple[str, ...]]:
    """One unconfirmed line per request line that has a useful one, and a note for each that was left out
    because it costs no less than the confirmed stock that covers the line (review P2, item W4)."""
    lines: list[OfferLine | None] = []
    notes: list[str] = []
    for outcome, pool, confirmed in zip(outcomes, pools, cheapest, strict=True):
        line = _unconfirmed_line(outcome, pool, now)
        covered = sum((each.covers for each in confirmed), ZERO)
        confirmed_net = sum((each.net for each in confirmed), ZERO)
        if line is not None and covered >= (outcome.need.quantity or ZERO) and line.net >= confirmed_net:
            notes.append(
                f"{line_label(outcome.need.index)}: {line.product_id}, whose quantity Valio does not confirm, would "
                f"cost {eur(line.net)}, not less than the {eur(confirmed_net)} of confirmed stock that covers the "
                "whole quantity, so it is not offered as an alternative."
            )
            line = None
        lines.append(line)
    return lines, tuple(notes)


def _unconfirmed_line(outcome: LineOutcome, pool: _Pools, now: datetime) -> OfferLine | None:
    """The fitting product in state QUANTITY_NOT_CONFIRMED with the lowest total for the whole quantity asked,
    whole packs counted, as the confirmed fill chooses (`tta.offers.combining`): 0.4 kg of sugar is one 500 g
    pack at €1.98, not a 25 kg sack at €24.27 that costs less per kilogram. The price per kilogram or litre
    only breaks a tie. Among the products whose data rules out every excluded allergen if there is one, and a
    regular product before a variant nobody asked for."""
    need = outcome.need
    if not pool.unconfirmed or need.quantity is None:
        return None
    quantity = need.quantity
    cheapest = min(
        pool.unconfirmed,
        key=lambda each: (
            not ruled_out(each.allergen_check), _is_variant(outcome.asked, each), _total_for(each, quantity),
            _price_per_requested_unit(each), each.product.id,
        ),
    )
    # The quantity is the one asked for. The amount Valio reports is a placeholder and is never read here.
    return line_for(cheapest, need, units_needed(cheapest, need.quantity), need.quantity, now)


def _total_for(candidate: Candidate, quantity: Decimal) -> Decimal:
    """What the quantity costs in whole sales units of the product, net."""
    return units_needed(candidate, quantity) * candidate.unit_price


def _price_per_requested_unit(candidate: Candidate) -> Decimal:
    return candidate.unit_price / (candidate.per_unit or Decimal(1))


def _flatten(groups: Sequence[tuple[OfferLine, ...]]) -> tuple[OfferLine, ...]:
    return tuple(line for group in groups for line in group)


def _swapped(
    confirmed: Sequence[tuple[OfferLine, ...]], replacements: Sequence[OfferLine | None]
) -> tuple[OfferLine, ...]:
    """The confirmed lines, with the lines of a request line replaced where a replacement exists."""
    groups = [(new,) if new is not None else old for old, new in zip(confirmed, replacements, strict=True)]
    return _flatten(groups)


def _extended(
    confirmed: Sequence[tuple[OfferLine, ...]], additions: Sequence[OfferLine | None]
) -> tuple[OfferLine, ...]:
    """The confirmed lines, each request line followed by the line that fills what it leaves missing."""
    groups = [(*old, new) if new is not None else old for old, new in zip(confirmed, additions, strict=True)]
    return _flatten(groups)
