"""Substitutes for one product: candidates, re-check, ranking, and what the buyer gives up (SPEC section 5).

Candidates: the pairs Valio lists, then the same 5-digit category, then the same first 4 digits, then
the same first 3. Every candidate is re-checked for price and availability in one call each. A candidate
that fails the allergen rules is shown with its reason and can never be ordered.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from tta.allergens import check_substitute
from tta.contracts.allergen import SubstituteAllergenCheck
from tta.contracts.availability import ClaimCheck, PriceLine
from tta.contracts.common import ExclusionReason, PackPreference
from tta.contracts.offer import SubstituteCandidate, SubstituteQuery, SubstituteResult
from tta.contracts.policy import BuyerProfile
from tta.contracts.ports import Catalog
from tta.contracts.product import PackSize, Product
from tta.contracts.request import MAX_PRODUCT_IDS
from tta.offers.candidates import (
    Candidate,
    Need,
    claims_of,
    evaluate,
    exclusion_for,
    named_product,
    price_problem,
    unconfirmed_gating,
    units_needed,
)
from tta.offers.deps import Lookup, OfferDeps, look_up
from tta.offers.substitute_wording import gives_up, why
from tta.offers.wording import counted

# One price call and one availability call hold 1,000 ids (SPEC section 5), the original included.
MAX_POOL = MAX_PRODUCT_IDS - 1
# Good, better, best: the search widens to the next category tier until three candidates can be ordered.
ENOUGH_ORDERABLE = 3
# Our limit on candidates Valio does not list, so an agent reads a short ranked list. Listed ones are all shown.
MAX_UNLISTED_SHOWN = 10
# (digits of the category shared, category distance): 0 same 5-digit category, 1 same first 4, 2 same first 3.
CATEGORY_TIERS = ((5, 0), (4, 1), (3, 2))
# A substitute Valio lists from a category that shares fewer than three digits (4 of the 249 listed pairs).
DISTANCE_OUTSIDE = 3
ALLERGEN_REASONS = (ExclusionReason.SUBSTITUTE_ADDS_ALLERGEN, ExclusionReason.ALLERGEN_DECLARED)
_UNKNOWN_LAST = (1, Decimal(0))

RankKey = Callable[["Judged"], tuple[object, ...]]


@dataclass(frozen=True)
class Judged:
    """One substitute candidate with everything the ranking and the offer need."""

    candidate: Candidate
    listed: bool
    distance: int
    rule: SubstituteAllergenCheck
    reason: ExclusionReason | None  # why it cannot be ordered; None when it can
    reason_sentence: str
    units: Decimal | None  # sales units for the quantity asked, when one was asked and the pack size is known
    claims: tuple[ClaimCheck, ...]

    @property
    def passes(self) -> bool:
        """Passes the allergen rules of SPEC section 6: adds no allergen, declares none the buyer excludes."""
        return self.reason not in ALLERGEN_REASONS

    @property
    def orderable(self) -> bool:
        return self.reason is None


@dataclass(frozen=True)
class Ranking:
    original: Product
    original_price: PriceLine | None
    original_pack: PackSize
    ranked: tuple[Judged, ...]
    lookup: Lookup
    notes: tuple[str, ...]


def find_substitutes(
    product_id: str, profile: BuyerProfile, deps: OfferDeps, query: SubstituteQuery | None = None
) -> SubstituteResult:
    """Ranked substitutes for one product, each with pass or fail and the reason. Raises `UnknownProduct`."""
    query = query or SubstituteQuery()
    original = named_product(deps.catalog, product_id)
    need = Need(
        index=0,
        quantity=query.quantity,
        unit=query.unit,
        pack=PackPreference.ANY,
        excluded=profile.excluded_allergens,
        strictness=profile.allergen_strictness if profile.excluded_allergens else None,
        needed_by=query.needed_by,
        require_confirmed=False,  # every candidate is shown with its status; the offer applies confirmed-only
    )
    ranking = rank_substitutes(original, need, deps)
    return SubstituteResult(
        original_id=original.id,
        original_name=original.display_name,
        candidates=tuple(_candidate(rank, judged, ranking) for rank, judged in enumerate(ranking.ranked, start=1)),
        source=ranking.lookup.source,
        time_now=ranking.lookup.now,
        notes=ranking.notes,
    )


def rank_substitutes(original: Product, need: Need, deps: OfferDeps, skip: Sequence[str] = ()) -> Ranking:
    """Judge and rank the candidates for `original`; `skip` names products that must not stand in."""
    pool = _pool(original, deps.catalog, frozenset(skip))
    lookup = look_up(deps, (original.id, *(product.id for product, _, _ in pool)))
    original_seen = evaluate(original, need, lookup, deps.catalog)
    judged = [_judge(product, is_listed, distance, original, need, lookup, deps.catalog)
              for product, is_listed, distance in pool]
    key = _rank_key(original_seen, need)
    shown, notes = _shown(judged, key)
    return Ranking(
        original=original,
        original_price=original_seen.price if price_problem(original_seen.price, lookup.now) is None else None,
        original_pack=original_seen.pack,
        ranked=tuple(sorted(shown, key=key)),
        lookup=lookup,
        notes=(*notes, *_pool_notes(pool)),
    )


def substitute_distance(original: Product, other: Product) -> int:
    for digits, distance in CATEGORY_TIERS:
        if original.category[:digits] == other.category[:digits]:
            return distance
    return DISTANCE_OUTSIDE


def _pool(original: Product, catalog: Catalog, skip: frozenset[str]) -> list[tuple[Product, bool, int]]:
    """(product, listed by Valio, category distance): the listed pairs first, then the category tiers."""
    seen = {original.id, *skip}
    pool: list[tuple[Product, bool, int]] = []
    listed = [catalog.get_product(product_id) for product_id in catalog.listed_substitutes(original.id)]
    tiers = [(product, True, substitute_distance(original, product)) for product in listed if product is not None]
    for digits, distance in CATEGORY_TIERS:
        tiers.extend((product, False, distance) for product in catalog.same_category(original.id, digits))
    for product, is_listed, distance in tiers:
        if product.id in seen or product.deleted:
            continue
        if len(pool) >= MAX_POOL:
            break
        seen.add(product.id)
        pool.append((product, is_listed, distance))
    return pool


def _pool_notes(pool: Sequence[tuple[Product, bool, int]]) -> tuple[str, ...]:
    if len(pool) < MAX_POOL:
        return ()
    return (f"Only the first {MAX_POOL} candidates were checked: one price and one availability call hold no more.",)


def _judge(
    product: Product, is_listed: bool, distance: int, original: Product, need: Need, lookup: Lookup, catalog: Catalog
) -> Judged:
    candidate = evaluate(product, need, lookup, catalog)
    rule = check_substitute(original.allergen_statements, product.allergen_statements)
    if rule.passes:
        dropped = exclusion_for(candidate, need, lookup.now)
    else:
        # The substitution rule holds for every buyer and is named before any other reason (SPEC section 6).
        dropped = (ExclusionReason.SUBSTITUTE_ADDS_ALLERGEN, rule.sentence)
    units = None
    if need.quantity is not None and candidate.per_unit is not None:
        units = units_needed(candidate, need.quantity)
    return Judged(
        candidate=candidate,
        listed=is_listed,
        distance=distance,
        rule=rule,
        reason=dropped[0] if dropped is not None else None,
        reason_sentence=dropped[1] if dropped is not None else "",
        units=units,
        claims=claims_of(candidate, need, units, lookup.now),
    )


def _shown(judged: Sequence[Judged], rank_key: RankKey) -> tuple[list[Judged], tuple[str, ...]]:
    """Every listed candidate, and the category tiers needed to reach three that can be ordered."""
    shown = [each for each in judged if each.listed]
    unlisted: list[Judged] = []
    for _, distance in CATEGORY_TIERS:
        if sum(each.orderable for each in (*shown, *unlisted)) >= ENOUGH_ORDERABLE:
            break
        unlisted.extend(each for each in judged if not each.listed and each.distance == distance)
    # Those that can be ordered first, so the limit never hides one behind candidates that cannot.
    kept = sorted(unlisted, key=lambda each: (not each.orderable, rank_key(each)))[:MAX_UNLISTED_SHOWN]
    notes = [f"{counted(len(judged), 'candidate')} checked for price, availability and allergens."]
    if len(unlisted) > len(kept):
        notes.append(
            f"{len(unlisted) - len(kept)} more from the same category tiers are not shown: "
            "they cannot be ordered or rank lower."
        )
    return [*shown, *kept], tuple(notes)


def _rank_key(original: Candidate, need: Need) -> RankKey:
    """Passes the allergen rules, category distance, listed by Valio, pack size closest to the original,
    verification status, price difference (SPEC section 5, "Ranking")."""

    def key(each: Judged) -> tuple[object, ...]:
        candidate = each.candidate
        unconfirmed = len(unconfirmed_gating(each.claims, dated=need.dated))
        verification = (not each.orderable, unconfirmed, _shortfall(candidate, need))
        return (
            not each.passes,
            each.distance,
            not each.listed,
            _pack_gap(original.pack, candidate.pack),
            verification,
            _price_gap(original, candidate),
            candidate.product.id,
        )

    return key


def _shortfall(candidate: Candidate, need: Need) -> Decimal:
    """How much of the quantity asked confirmed stock leaves uncovered, in the request's unit; 0 when not known."""
    usable = candidate.assessment.usable_amount
    if need.quantity is None or candidate.per_unit is None or usable is None:
        return Decimal(0)
    return max(need.quantity - usable * candidate.per_unit, Decimal(0))


def _pack_gap(original: PackSize, other: PackSize) -> tuple[int, Decimal]:
    if not (original.is_known and other.is_known) or original.unit is not other.unit:
        return _UNKNOWN_LAST
    if original.value is None or other.value is None:
        return _UNKNOWN_LAST
    return 0, abs(other.value - original.value)


def _price_gap(original: Candidate, other: Candidate) -> tuple[int, Decimal]:
    """Cheaper first, compared per litre or kilogram when both sizes are known, else per sales unit."""
    if not (_has_price(original) and _has_price(other)):
        return _UNKNOWN_LAST
    comparable = _pack_gap(original.pack, other.pack) != _UNKNOWN_LAST
    if comparable and original.pack.value and other.pack.value:
        return 0, other.unit_price / other.pack.value - original.unit_price / original.pack.value
    return 0, other.unit_price - original.unit_price


def _has_price(candidate: Candidate) -> bool:
    return candidate.price is not None and candidate.price.has_price


def _candidate(rank: int, judged: Judged, ranking: Ranking) -> SubstituteCandidate:
    candidate = judged.candidate
    usable_price = price_problem(candidate.price, ranking.lookup.now) is None
    unit_price = candidate.unit_price if usable_price else None
    original_price = ranking.original_price
    difference = None
    if unit_price is not None and original_price is not None and original_price.catalog_price is not None:
        difference = unit_price - original_price.catalog_price.value
    return SubstituteCandidate(
        rank=rank,
        product_id=candidate.product.id,
        name=candidate.product.display_name,
        passes=judged.passes,
        orderable=judged.orderable,
        reason=judged.reason,
        sentence=why(judged),
        gives_up=gives_up(judged, ranking),
        listed_by_supplier=judged.listed,
        category_distance=judged.distance,
        pack_size=candidate.pack,
        availability=candidate.assessment,
        claims=judged.claims,
        allergen_check=judged.rule,
        unit_net_price=unit_price,
        price_difference=difference,
    )
