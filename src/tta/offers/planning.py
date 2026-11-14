"""Which lines go into which option (SPEC section 5, step 3).

BEST_CONFIRMED uses confirmed stock only, ranked by the buyer's preference and then price (task SUST-1).
CHEAPEST_CONFIRMED is the price fill of the same stock, when a preference other than price chose another one.
ALTERNATIVE_UNCONFIRMED is the cheapest fitting product whose quantity Valio does not confirm. SUBSTITUTE keeps
the confirmed stock of a product named by id and fills what is missing with the best substitute.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal

from tta.contracts.common import AvailabilityState, ExclusionReason, OptionKind, Preference
from tta.contracts.offer import Exclusion, OfferLine, SubstituteInfo
from tta.contracts.product import Product
from tta.contracts.request import RequestLine
from tta.offers.candidates import Candidate, Need, units_needed
from tta.offers.combining import Fill, Supply, fill, floor_to_step
from tta.offers.deps import OfferDeps
from tta.offers.lines import line_for
from tta.offers.options import Draft
from tta.offers.preference import PRICE_TIER, tiers
from tta.offers.substitute_wording import gives_up
from tta.offers.substitutes import Judged, Ranking, rank_substitutes
from tta.offers.wording import counted, line_label, listed, plain_name

ZERO = Decimal(0)
CONFIRMED_ONLY = "confirmed data only was asked for"
# What the note says of the products that dropped out for a reason that exists only under confirmed-only.
LEFT_OUT_UNDER_CONFIRMED_ONLY = {
    ExclusionReason.QUANTITY_NOT_CONFIRMED: "whose quantity Valio does not confirm",
    ExclusionReason.DELIVERY_DATE_NOT_CONFIRMED: "whose delivery date Valio's data does not confirm",
}


@dataclass(frozen=True)
class LineOutcome:
    """One request line after every candidate was judged."""

    need: Need
    asked: RequestLine
    considered: int
    fitting: tuple[Candidate, ...]  # passed every exclusion check; state CONFIRMED or QUANTITY_NOT_CONFIRMED
    excluded: tuple[Exclusion, ...]


@dataclass(frozen=True)
class Plan:
    drafts: tuple[Draft, ...]
    notes: tuple[str, ...]


@dataclass(frozen=True)
class _Pools:
    confirmed: tuple[Candidate, ...]
    unconfirmed: tuple[Candidate, ...]
    notes: tuple[str, ...]


def plan_options(
    outcomes: Sequence[LineOutcome], now: datetime, deps: OfferDeps, prefer: Preference = Preference.PRICE
) -> Plan:
    pools = [_pools(outcome) for outcome in outcomes]
    fills = _confirmed_fills(outcomes, pools, prefer)
    confirmed = _all_confirmed_lines(outcomes, pools, fills, now)
    alternatives = [_unconfirmed_line(outcome, pool, now) for outcome, pool in zip(outcomes, pools, strict=True)]
    substitutes, substitute_notes = _substitute_lines(outcomes, fills, deps)
    drafts = [Draft(OptionKind.BEST_CONFIRMED, _flatten(confirmed))]
    if prefer is not Preference.PRICE:
        drafts.extend(_cheapest(outcomes, pools, fills, now))
    if any(alternatives):
        drafts.append(Draft(OptionKind.ALTERNATIVE_UNCONFIRMED, _swapped(confirmed, alternatives)))
    if any(substitutes):
        drafts.append(Draft(OptionKind.SUBSTITUTE, _extended(confirmed, substitutes)))
    kept, filter_notes = _confirmed_only(outcomes, [draft for draft in drafts if draft.lines])
    notes = [note for pool in pools for note in pool.notes]
    return Plan(drafts=tuple(kept), notes=(*notes, *substitute_notes, *filter_notes))


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
    return _Pools(confirmed, unconfirmed, _confirmed_only_notes(outcome))


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


def _cheapest(
    outcomes: Sequence[LineOutcome], pools: Sequence[_Pools], preferred: Sequence[Fill], now: datetime
) -> tuple[Draft, ...]:
    """The price fill of the same confirmed stock, when it picks other products or amounts than the preferred
    fill. Whether it is also cheaper is judged on the totals (`tta.offers.options`)."""
    cheapest = _confirmed_fills(outcomes, pools, Preference.PRICE)
    if [each.picks for each in cheapest] == [each.picks for each in preferred]:
        return ()
    return (Draft(OptionKind.CHEAPEST_CONFIRMED, _flatten(_all_confirmed_lines(outcomes, pools, cheapest, now))),)


def _all_confirmed_lines(
    outcomes: Sequence[LineOutcome], pools: Sequence[_Pools], fills: Sequence[Fill], now: datetime
) -> list[tuple[OfferLine, ...]]:
    return [
        _confirmed_lines(outcome, pool, picked, now)
        for outcome, pool, picked in zip(outcomes, pools, fills, strict=True)
    ]


def _supply(candidate: Candidate, already_used: Decimal = ZERO, tier: int = PRICE_TIER) -> Supply:
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


def _confirmed_fills(outcomes: Sequence[LineOutcome], pools: Sequence[_Pools], prefer: Preference) -> list[Fill]:
    """One fill per request line, in order. Stock one line takes is not offered to the next."""
    used: Mapping[str, Decimal] = {}
    fills: list[Fill] = []
    for outcome, pool in zip(outcomes, pools, strict=True):
        tier = tiers(pool.confirmed, prefer)
        supplies = [_supply(each, used.get(each.product.id, ZERO), tier[each.product.id]) for each in pool.confirmed]
        picked = fill(outcome.need.quantity or ZERO, supplies)
        used = _with_picks(used, picked)
        fills.append(picked)
    return fills


def _with_picks(used: Mapping[str, Decimal], picked: Fill) -> Mapping[str, Decimal]:
    added = {pick.product_id: used.get(pick.product_id, ZERO) + pick.units for pick in picked.picks}
    return {**used, **added}


def _confirmed_lines(outcome: LineOutcome, pool: _Pools, picked: Fill, now: datetime) -> tuple[OfferLine, ...]:
    by_id = {each.product.id: each for each in pool.confirmed}
    return tuple(line_for(by_id[pick.product_id], outcome.need, pick.units, pick.covers, now) for pick in picked.picks)


def _unconfirmed_line(outcome: LineOutcome, pool: _Pools, now: datetime) -> OfferLine | None:
    """The cheapest fitting product in state QUANTITY_NOT_CONFIRMED, for the whole quantity asked."""
    need = outcome.need
    if not pool.unconfirmed or need.quantity is None:
        return None
    cheapest = min(pool.unconfirmed, key=lambda each: (_price_per_requested_unit(each), each.product.id))
    # The quantity is the one asked for. The amount Valio reports is a placeholder and is never read here.
    return line_for(cheapest, need, units_needed(cheapest, need.quantity), need.quantity, now)


def _price_per_requested_unit(candidate: Candidate) -> Decimal:
    return candidate.unit_price / (candidate.per_unit or Decimal(1))


def _substitute_lines(
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
        used = _with_picks(used, picked)
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
    for judged in ranking.ranked:
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
    )
    return line_for(candidate, need, units, min(units * candidate.per_unit, need.quantity), now, info)


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
