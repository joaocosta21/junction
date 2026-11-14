"""Substitutes for one product: candidates, re-check, ranking, and what the buyer gives up (SPEC section 5).

Candidates: the pairs Valio lists, then the products of the same 5-digit category, and nothing wider. A
category number is opaque: Valio did not confirm that its digits are levels (answer V7, 14 Nov 2026), and a
shared prefix is a neighbouring shelf, not the same kind of product (AIMO/build/replan/P7-categories.md).
Every candidate is re-checked for price and availability in one call each.

The order of the gates (AIMO/build/replan/P10-formula.md section 4.4), first decides first:

0. The allergen rule. A candidate that fails it is shown with its reason and can never be ordered.
1. The dietary claims. A candidate that loses one is a last resort (Valio, answer B7): it is held back while
   a candidate that keeps them all can be ordered, and when shown it still goes to a human (rule F-08).
2. Is it the same kind of product (ours, decided by the team on 14 Nov 2026; `tta.catalog.kinds`)? A candidate
   of another product type than the original, or a flavoured one for a plain one (and a plain one for a
   flavoured one), is a last resort like a claim-loser. A pair Valio lists stays when only the type differs,
   after every candidate of the same type. Another use (made for coffee, for whipping, for cooking) and
   another flavour of a flavoured product only order the candidates.
3. The formula (`tta.offers.formula`): same product in another pack, same brand, other brand, different,
   not known. It only orders the candidates; nothing is hidden by it.
4. Listed by Valio, pack size closest, verification, price.

Each candidate carries a `ReplaceCheck`: one sentence that says whether it can replace the original like for
like, and each reason why not.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal

from tta.allergens import check_substitute
from tta.catalog.kinds import flavours_of, is_other_use, is_same_type, product_types_of, uses_of
from tta.contracts.allergen import SubstituteAllergenCheck
from tta.contracts.availability import ClaimCheck, PriceLine
from tta.contracts.common import ExclusionReason, PackPreference, Unit
from tta.contracts.offer import SubstituteCandidate, SubstituteQuery, SubstituteResult
from tta.contracts.policy import BuyerProfile
from tta.contracts.ports import Catalog
from tta.contracts.product import FormulaCheck, FormulaOutcome, PackSize, Product, ReplaceCheck, ReplaceVerdict
from tta.contracts.request import MAX_PRODUCT_IDS
from tta.offers.candidates import (
    Candidate,
    Need,
    allergen_rules,
    claims_of,
    evaluate,
    exclusion_for,
    named_product,
    price_problem,
    unconfirmed_gating,
    units_needed,
)
from tta.offers.deps import Lookup, OfferDeps, look_up
from tta.offers.formula import compare_formula
from tta.offers.substitute_wording import (
    gives_up,
    per_measure_difference,
    replace_reasons,
    replace_sentence,
    why,
)
from tta.offers.wording import counted, measured

# One price call and one availability call hold 1,000 ids (SPEC section 5), the original included.
MAX_POOL = MAX_PRODUCT_IDS - 1
# Our limit on candidates Valio does not list, so an agent reads a short ranked list. Listed ones are all shown.
MAX_UNLISTED_SHOWN = 10
# Category distance takes two values: the same 5-digit category, or another one. Another category is only ever
# a pair Valio lists (20 of the 249 listed pairs, whole catalog): no unlisted candidate comes from one.
DISTANCE_SAME_CATEGORY = 0
DISTANCE_OTHER_CATEGORY = 1
ALLERGEN_REASONS = (ExclusionReason.SUBSTITUTE_ADDS_ALLERGEN, ExclusionReason.ALLERGEN_DECLARED)
# The claims a buyer relies on for a diet or an intolerance. The list is ours: picked from the 21 claim
# codes of the catalog (AIMO/docs/PRODUCT-DATA.md section 3.4). Only these count as a claim lost: they
# order the candidates and rule F-08 reads them. The other 13 (preservatives, colouring agents, additives,
# sugars, sweeteners, fibre, protein, salt, fat, GMO) are named in `gives_up` and change neither.
DIETARY_CLAIMS = frozenset(
    {
        "FREE_FROM_LACTOSE",
        "LOW_LACTOSE",
        "FREE_FROM_GLUTEN",
        "FREE_FROM_WHEAT",
        "FREE_FROM_EGGS",
        "FREE_FROM_SOY",
        "VEGAN",
        "VEGETARIAN",
    }
)
# A claim that another claim covers: a product that carries the stronger one has not lost the weaker one. A
# lactose-free product is also low in lactose, and a vegan product is also vegetarian. Nothing else is covered:
# gluten-free does not cover wheat-free (decision D4 of AIMO/build/replan/P9b-booth-answers.md; the list is ours).
COVERED_BY: Mapping[str, frozenset[str]] = {
    "LOW_LACTOSE": frozenset({"FREE_FROM_LACTOSE"}),
    "VEGETARIAN": frozenset({"VEGAN"}),
}
# Best first: where the formula stands in the ranking key, after the dietary claims.
FORMULA_ORDER = {
    FormulaOutcome.SAME_PRODUCT_OTHER_PACK: 0,
    FormulaOutcome.SAME_BRAND: 1,
    FormulaOutcome.OTHER_BRAND: 2,
    FormulaOutcome.DIFFERENT: 3,
    FormulaOutcome.NOT_KNOWN: 4,
}
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
    claims_lost: tuple[str, ...]  # dietary claims of the original that this product does not carry
    claims_not_carried: tuple[str, ...]  # every claim of the original it does not carry, dietary or not
    formula: FormulaCheck  # its composition measured against the original's
    replaceable: ReplaceCheck  # same kind of product as the original, or each reason why not
    # It loses a dietary claim or is another kind of product, and is shown only because no candidate that
    # keeps every claim and is the same kind can be ordered.
    last_resort: bool = False

    @property
    def passes(self) -> bool:
        """Passes the allergen rules of SPEC section 6: adds no allergen, declares none the buyer excludes."""
        return self.reason not in ALLERGEN_REASONS

    @property
    def orderable(self) -> bool:
        return self.reason is None

    @property
    def other_kind(self) -> bool:
        """Not the same kind of product: flavoured against plain, or another product type that Valio does not
        list for the original. Such a candidate leaves the list while a like-for-like one can be ordered."""
        check = self.replaceable
        return check.plain_against_flavoured or (check.other_type and not self.listed)


@dataclass(frozen=True)
class Ranking:
    original: Product
    original_price: PriceLine | None
    original_pack: PackSize
    ranked: tuple[Judged, ...]
    lookup: Lookup
    notes: tuple[str, ...]
    asked: Need  # the need as it was asked
    # The need the candidates were judged against: `asked`, or its quantity turned into litres or kilograms
    # when it was in pieces and the original's content is known (`_by_content`).
    need: Need
    per_piece: Decimal | None = None  # litres or kilograms in one sales unit of the original, when converted


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
        strictness_by_code=allergen_rules(profile, profile.excluded_allergens),
        needed_by=query.needed_by,
        # The buyer's own rules, as its offer applies them: a candidate the offer would exclude is shown with
        # the same reason and sentence and cannot be ordered (task FIX-12b). A substitute query has no
        # request, so the profile's setting is the only source of confirmed-only here.
        require_confirmed=profile.require_confirmed,
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
    asked = need
    need, per_piece = _by_content(evaluate(original, asked, lookup, deps.catalog), asked)
    original_seen = evaluate(original, need, lookup, deps.catalog)
    judged = [_judge(product, is_listed, distance, original, need, lookup, deps.catalog)
              for product, is_listed, distance in pool]
    key = _rank_key(original_seen, need)
    kept, held_back = _hold_back_last_resorts(judged)
    shown, notes = _shown(kept, key, checked=len(judged))
    return Ranking(
        original=original,
        original_price=original_seen.price if price_problem(original_seen.price, lookup.now) is None else None,
        original_pack=original_seen.pack,
        ranked=tuple(sorted(shown, key=key)),
        lookup=lookup,
        notes=(*notes, *held_back, *_pool_notes(pool), *_content_note(asked, need, per_piece)),
        asked=asked,
        need=need,
        per_piece=per_piece,
    )


def _by_content(original: Candidate, need: Need) -> tuple[Need, Decimal | None]:
    """A quantity in pieces of the original, as litres or kilograms (Valio, answer Q14 of 14 Nov 2026: "the
    goal is to satisfy the prompt"; review P9b, item Q14-1). 100 cartons of 1 L are 100 L: a case of 10 L
    stands in 10 times, not 100. A candidate whose content is not known in that measure can then not be
    ordered (`PACK_SIZE_UNKNOWN`). Where the original's own content is not known, pieces stay pieces.
    """
    pack = original.pack
    if need.unit is not Unit.UNIT or need.quantity is None or not pack.is_known or not pack.value or not pack.unit:
        return need, None
    return replace(need, quantity=need.quantity * pack.value, unit=pack.unit), pack.value


def _content_note(asked: Need, need: Need, per_piece: Decimal | None) -> tuple[str, ...]:
    if per_piece is None or asked.quantity is None or need.quantity is None:
        return ()
    return (
        f"{measured(asked.quantity, asked.unit)} of the product asked for hold {measured(need.quantity, need.unit)}"
        f": each candidate is counted by its content, not one sales unit for one.",
    )


def substitute_distance(original: Product, other: Product) -> int:
    """0 for the same 5-digit category, 1 for any other. The digits are never read as levels."""
    return DISTANCE_SAME_CATEGORY if original.category == other.category else DISTANCE_OTHER_CATEGORY


def _pool(original: Product, catalog: Catalog, skip: frozenset[str]) -> list[tuple[Product, bool, int]]:
    """(product, listed by Valio, category distance): the listed pairs first, then the same 5-digit category."""
    seen = {original.id, *skip}
    pool: list[tuple[Product, bool, int]] = []
    listed = [catalog.get_product(product_id) for product_id in catalog.listed_substitutes(original.id)]
    found = [(product, True, substitute_distance(original, product)) for product in listed if product is not None]
    found.extend((product, False, DISTANCE_SAME_CATEGORY) for product in catalog.same_category(original.id, 5))
    for product, is_listed, distance in found:
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
        claims_lost=(lost := claims_lost(original, product)),
        claims_not_carried=claims_not_carried(original, product),
        formula=(formula := compare_formula(original, product)),
        replaceable=replace_check(original, product, formula, lost, listed=is_listed),
    )


def replace_check(
    original: Product, other: Product, formula: FormulaCheck, lost: Sequence[str] = (), *, listed: bool = False
) -> ReplaceCheck:
    """Can `other` take the original's place like for like? Type, flavour and use are read from the product
    file (`tta.catalog.kinds`, word lists ours); the formula and the dietary claims lost are given.

    Where the original has no product type of ours, the type is not judged.
    """
    original_types, types = product_types_of(original), product_types_of(other)
    original_flavours, flavours = flavours_of(original), flavours_of(other)
    original_uses, uses = uses_of(original), uses_of(other)
    facts = ReplaceCheck(
        verdict=ReplaceVerdict.REPLACEABLE,
        original_types=original_types,
        types=types,
        other_type=bool(original_types) and not is_same_type(original_types, types),
        original_flavours=original_flavours,
        flavours=flavours,
        plain_against_flavoured=bool(original_flavours) is not bool(flavours),
        other_flavour=bool(original_flavours) and bool(flavours) and original_flavours != flavours,
        original_uses=original_uses,
        uses=uses,
        other_use=is_other_use(original_uses, uses),
        sentence="",
    )
    reasons = replace_reasons(facts, formula, lost, listed=listed)
    if reasons:
        verdict = ReplaceVerdict.NOT_LIKE_FOR_LIKE
    elif formula.outcome is FormulaOutcome.NOT_KNOWN:
        verdict = ReplaceVerdict.NOT_SHOWN  # NOT_KNOWN is never read as the same formula
    else:
        verdict = ReplaceVerdict.REPLACEABLE
    same_category = original.category == other.category
    return facts.model_copy(
        update={
            "verdict": verdict,
            "reasons": reasons,
            "sentence": replace_sentence(facts, verdict, reasons, same_category=same_category),
        }
    )


def claims_not_carried(original: Product, other: Product) -> tuple[str, ...]:
    """Every nutritional claim of the original that `other` neither carries nor covers, in the original's order.

    `COVERED_BY`: a lactose-free product has not lost LOW_LACTOSE, a vegan one has not lost VEGETARIAN.
    """
    carried = frozenset(other.nutritional_claims)
    return tuple(
        dict.fromkeys(
            claim
            for claim in original.nutritional_claims
            if claim not in carried and not COVERED_BY.get(claim, frozenset()) & carried
        )
    )


def claims_lost(original: Product, other: Product) -> tuple[str, ...]:
    """The original's dietary claims (`DIETARY_CLAIMS`) that `other` neither carries nor covers, in order.

    A claim is not an allergen statement, so the allergen rule does not see one that is lost: a
    lactose-free milk and a regular milk both declare milk (AIMO/docs/SCHEMA-AND-CODES.md section 4).
    """
    return tuple(claim for claim in claims_not_carried(original, other) if claim in DIETARY_CLAIMS)


def _is_last_resort(each: Judged) -> bool:
    return each.passes and (bool(each.claims_lost) or each.other_kind)


def _hold_back_last_resorts(judged: Sequence[Judged]) -> tuple[list[Judged], tuple[str, ...]]:
    """A candidate that loses a dietary claim is a last resort (Valio, answer B7, clarified 14 Nov 2026), and
    so is one that is another kind of product (`Judged.other_kind`; ours, decided on 14 Nov 2026).

    While at least one candidate that keeps every dietary claim and is the same kind can be ordered, the last
    resorts leave the list, and a note says how many. The offer reads the same list, so it cannot take one
    either. When no such candidate can be ordered they stay, marked `last_resort`; rule F-08 sends a
    claim-loser to a human. A candidate that fails the allergen rule is not held back: it is shown with its
    reason and cannot be ordered.
    """
    last_resorts = [each for each in judged if _is_last_resort(each)]
    if not last_resorts:
        return list(judged), ()
    if not any(each.orderable and not _is_last_resort(each) for each in judged):
        return [replace(each, last_resort=True) if _is_last_resort(each) else each for each in judged], ()
    held = {id(each) for each in last_resorts}
    notes = (*_claim_note(judged), *_other_kind_note(judged))
    return [each for each in judged if id(each) not in held], notes


def _claim_note(judged: Sequence[Judged]) -> tuple[str, ...]:
    losers = sum(each.passes and bool(each.claims_lost) for each in judged)
    if not losers:
        return ()
    keepers = sum(each.orderable and not each.claims_lost for each in judged)
    lack = "lacks" if losers == 1 else "lack"
    are = "is" if losers == 1 else "are"
    keep = "keeps" if keepers == 1 else "keep"
    return (
        f"{counted(losers, 'candidate')} that {lack} a dietary claim of the original {are} held back as a "
        f"last resort: {keepers} that {keep} every dietary claim can be ordered.",
    )


def _other_kind_note(judged: Sequence[Judged]) -> tuple[str, ...]:
    """The candidates held back for their kind alone; one that also loses a claim is counted in the claim note."""
    others = [each for each in judged if each.passes and each.other_kind and not each.claims_lost]
    if not others:
        return ()
    flavour = sum(each.replaceable.plain_against_flavoured for each in others)
    kind = sum(each.replaceable.other_type and not each.replaceable.plain_against_flavoured for each in others)
    same = sum(each.orderable and not _is_last_resort(each) for each in judged)
    why_not = " and ".join(
        part for part in (
            f"{flavour} flavoured where the original is not, or the reverse" if flavour else "",
            f"{kind} of another product type" if kind else "",
        ) if part
    )
    are = "is" if len(others) == 1 else "are"
    return (
        f"{counted(len(others), 'candidate')} that {are} not the same kind of product ({why_not}) {are} held "
        f"back as a last resort: {same} of the same kind can be ordered.",
    )


def _shown(judged: Sequence[Judged], rank_key: RankKey, checked: int) -> tuple[list[Judged], tuple[str, ...]]:
    """Every listed candidate, and the best of the same 5-digit category, `MAX_UNLISTED_SHOWN` at most.

    A candidate Valio lists that fails the allergen rule is shown with its reason: the buyer should see why
    Valio's own substitute is not offered. One that Valio does not list and that fails the rule is left out
    and counted in a note, so the list does not spend its places on products the buyer can never take (ours,
    decided on 14 Nov 2026).
    """
    shown = [each for each in judged if each.listed]
    failing = [each for each in judged if not each.listed and not each.passes]
    unlisted = [each for each in judged if not each.listed and each.passes]
    # Those that can be ordered first, so the limit never hides one behind candidates that cannot.
    kept = sorted(unlisted, key=lambda each: (not each.orderable, rank_key(each)))[:MAX_UNLISTED_SHOWN]
    notes = [f"{counted(checked, 'candidate')} checked for price, availability and allergens."]
    if len(unlisted) > len(kept):
        notes.append(
            f"{len(unlisted) - len(kept)} more of the same category are not shown: "
            "they cannot be ordered or rank lower."
        )
    if failing:
        fail = "fails" if len(failing) == 1 else "fail"
        are = "is" if len(failing) == 1 else "are"
        notes.append(
            f"{counted(len(failing), 'candidate')} of the same category that Valio does not list {fail} the "
            f"allergen rule and {are} not shown: each adds an allergen or declares one this buyer excludes."
        )
    return [*shown, *kept], tuple(notes)


def _rank_key(original: Candidate, need: Need) -> RankKey:
    """Passes the allergen rules, keeps every dietary claim of the original and is the same kind of product,
    same product type (only a pair Valio lists can differ here), same use, same flavour, formula outcome,
    listed by Valio, pack size closest to the original, verification status, price difference.

    Losing a dietary claim only orders the candidates that pass the allergen rules; it fails none of them.
    A claim that is not dietary does not order them at all. The formula comes after the dietary claims and
    can never lift a candidate over them: 469050 has the six figures of 469126 and is not lactose-free. The
    formula took the place of the category distance, which no longer orders anything: a pair Valio lists
    from another category is judged by what it is made of.
    """

    def key(each: Judged) -> tuple[object, ...]:
        candidate = each.candidate
        unconfirmed = len(unconfirmed_gating(each.claims, dated=need.dated))
        verification = (not each.orderable, unconfirmed, _shortfall(candidate, need))
        return (
            not each.passes,
            _is_last_resort(each),
            each.replaceable.other_type,
            each.replaceable.other_use,
            each.replaceable.other_flavour,
            FORMULA_ORDER[each.formula.outcome],
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
    per_measure = None
    if unit_price is not None and original_price is not None and original_price.catalog_price is not None:
        ours = original_price.catalog_price.value
        difference = unit_price - ours
        gap = per_measure_difference(ours, ranking.original_pack, unit_price, candidate.pack)
        per_measure = gap[0] if gap is not None else None
    return SubstituteCandidate(
        rank=rank,
        product_id=candidate.product.id,
        name=candidate.product.display_name,
        passes=judged.passes,
        orderable=judged.orderable,
        reason=judged.reason,
        sentence=why(judged),
        gives_up=gives_up(judged, ranking),
        claims_lost=judged.claims_lost,
        listed_by_supplier=judged.listed,
        category_distance=judged.distance,
        pack_size=candidate.pack,
        availability=candidate.assessment,
        claims=judged.claims,
        allergen_check=judged.rule,
        unit_net_price=unit_price,
        price_difference=difference,
        formula=judged.formula,
        last_resort=judged.last_resort,
        price_difference_per_requested_unit=per_measure,
        replaceable=judged.replaceable,
    )
