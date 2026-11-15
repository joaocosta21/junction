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
   Where no product type of ours says what the original is, or the type is raw meat or fish (the cut is the
   product), the name says it (`tta.catalog.kind_words`): a candidate whose name does not carry the original's
   kind words ("yolk", "brisket", "cocoa powder") is another product. It leaves the ranking altogether, so no
   caller can offer it, and a note counts it (decision B65). A pair Valio lists stays, and says so.
3. The formula (`tta.offers.formula`): same product in another pack, same brand, other brand, different,
   not known. It only orders the candidates; nothing is hidden by it. Where the formula matters for the line
   (`Need.formula_matters`: the request, the buyer's setting, or what the gateway learned of the buyer's
   orders says so), a candidate shown to keep the formula comes before the use and the flavour its name says,
   the original's brand first (`_keeper_place`); and a candidate of the original's brand whose formula cannot
   be compared comes before another brand's whose formula cannot be compared, never before one that is shown
   to keep it (`_formula_place`).
4. Listed by Valio, pack size closest, verification, price.

Each candidate carries a `ReplaceCheck`: one sentence that says whether it can replace the original like for
like, and each reason why not.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal

from tta.allergens import check_substitute, statement_for
from tta.catalog.kind_words import KindWords, count_category_words, kind_words, missing_kind_words, shared_weight
from tta.catalog.kinds import flavours_of, is_other_use, is_raw_type, is_same_type, product_types_of, uses_of
from tta.catalog.name_words import name_difference, shares_a_product_word
from tta.contracts.allergen import SubstituteAllergenCheck
from tta.contracts.availability import ClaimCheck, PriceLine
from tta.contracts.common import AllergenRelation, ExclusionReason, PackPreference, Unit
from tta.contracts.offer import SubstituteCandidate, SubstituteQuery, SubstituteResult
from tta.contracts.policy import BuyerProfile
from tta.contracts.ports import Catalog
from tta.contracts.product import FormulaCheck, FormulaOutcome, PackSize, Product, ReplaceCheck, ReplaceVerdict
from tta.contracts.request import MAX_PRODUCT_IDS
from tta.offers.candidates import (
    PROFILE_SAYS_FORMULA,
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
from tta.offers.formula import compare_formula, same_brand
from tta.offers.substitute_kind import kind_reason, other_kind_note
from tta.offers.substitute_trade_off import gives_up
from tta.offers.substitute_wording import (
    per_measure_difference,
    replace_reasons,
    replace_sentence,
    why,
)
from tta.offers.wording import counted, measured, plain_name

# One price call and one availability call hold 1,000 ids (SPEC section 5), the original included.
MAX_POOL = MAX_PRODUCT_IDS - 1
# Our limit on candidates Valio does not list, so an agent reads a short ranked list. Listed ones are all shown.
MAX_UNLISTED_SHOWN = 10
# Category distance takes two values: the same 5-digit category, or another one. Another category is only ever
# a pair Valio lists (20 of the 249 listed pairs, whole catalog): no unlisted candidate comes from one.
DISTANCE_SAME_CATEGORY = 0
DISTANCE_OTHER_CATEGORY = 1
# CLAIM_CONTRADICTED: the candidate's own allergen data contradicts a claim the request line requires.
ALLERGEN_REASONS = (
    ExclusionReason.SUBSTITUTE_ADDS_ALLERGEN, ExclusionReason.ALLERGEN_DECLARED, ExclusionReason.CLAIM_CONTRADICTED,
)
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
# The dietary claims that say how a person chooses to eat, not what a person cannot eat. Losing one of these
# alone does not put a product of the same kind behind another kind of product (`_rank_key`). The list is ours.
WAY_OF_EATING_CLAIMS = frozenset({"VEGAN", "VEGETARIAN"})
# A claim that another claim covers: a product that carries the stronger one has not lost the weaker one. A
# lactose-free product is also low in lactose, and a vegan product is also vegetarian. Nothing else is covered:
# gluten-free does not cover wheat-free (decision D4 of AIMO/build/replan/P9b-booth-answers.md; the list is ours).
COVERED_BY: Mapping[str, frozenset[str]] = {
    "LOW_LACTOSE": frozenset({"FREE_FROM_LACTOSE"}),
    "VEGETARIAN": frozenset({"VEGAN"}),
}
# A claim that the candidate's own allergen data states: a product whose data says "free from soybeans" has
# not lost FREE_FROM_SOY for want of the label (review finding C3-F9: the rice drink 473424). Only where the
# claim names one allergen and the data says FREE_FROM of exactly that code; "may contain", no statement and a
# general statement leave the claim lost. Gluten, wheat and lactose are not here: the claim promises more than
# the allergen statement does (a limit in the product, not only no such ingredient). The list is ours.
STATED_BY_ALLERGEN_DATA: Mapping[str, str] = {"FREE_FROM_SOY": "AY", "FREE_FROM_EGGS": "AE"}
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
    # How much of the original's kind its name says (`tta.catalog.kind_words.shared_weight`); 0 where the
    # original's kind is not read from its name.
    kind_said: int = 0

    @property
    def passes(self) -> bool:
        """Passes the allergen rules of SPEC section 6: adds no allergen, declares none the buyer excludes."""
        return self.reason not in ALLERGEN_REASONS

    @property
    def orderable(self) -> bool:
        return self.reason is None

    @property
    def other_kind(self) -> bool:
        """Not the same kind of product, or not shown to be: flavoured against plain; or, unless Valio lists
        the pair, another product type, or (for an original with no product type of ours) a name that shares
        no product word with the original's.
        Such a candidate leaves the list while a like-for-like one can be ordered."""
        check = self.replaceable
        return check.plain_against_flavoured or ((check.other_type or check.no_shared_word) and not self.listed)

    @property
    def unexplained_variant(self) -> bool:
        """A variant of the original's product line that nothing explains (review finding S11): the names
        differ in a word no list of ours knows, the six nutrition figures show no difference, and Valio does
        not list the pair. It is the same kind of product, so it stays in the list in its place, after the
        candidates of its formula class whose names differ in nothing; but it is always marked `last_resort`,
        so rule F-12 sends it to a person: the data cannot say that "high heat" and "instant" milk powder
        are the same in a kitchen.

        Where the figures do differ, the candidate is already "not like for like" for its formula and is
        ranked as any product of another formula; the words are still said. A pair Valio lists stays unmarked
        (Valio's own judgement) and says the words too. Ours, decided on 14 Nov 2026."""
        differs = self.replaceable.name_difference and self.formula.outcome is not FormulaOutcome.DIFFERENT
        return differs and not self.listed


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
        # Nor has it a request line to say that the formula matters: the buyer's setting for every line does.
        formula_said=(
            PROFILE_SAYS_FORMULA.format(buyer=plain_name(profile.display_name)) if profile.formula_matters else ""
        ),
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
    missing = missing_listed(original, deps.catalog)
    lookup = look_up(deps, (original.id, *(product.id for product, _, _ in pool)))
    asked = need
    need, per_piece = _by_content(evaluate(original, asked, lookup, deps.catalog), asked)
    original_seen = evaluate(original, need, lookup, deps.catalog)
    kind = _kind_by_name(original, deps.catalog)
    checked = [_judge(product, is_listed, distance, original, need, lookup, deps.catalog, kind)
               for product, is_listed, distance in pool]
    judged, other_products = _leave_out_other_products(checked)
    key = _rank_key(original_seen, need)
    kept, held_back = _hold_back_last_resorts(judged)
    kept = [replace(each, last_resort=True) if each.passes and each.unexplained_variant else each for each in kept]
    shown, notes = _shown(kept, key, checked=len(checked))
    return Ranking(
        original=original,
        original_price=original_seen.price if price_problem(original_seen.price, lookup.now) is None else None,
        original_pack=original_seen.pack,
        ranked=tuple(sorted(shown, key=key)),
        lookup=lookup,
        notes=(*notes, *other_kind_note(original, len(other_products), sum(each.passes for each in judged)),
               *held_back,
               *_missing_note(missing), *_pool_notes(pool), *_content_note(asked, need, per_piece)),
        asked=asked,
        need=need,
        per_piece=per_piece,
    )


def _kind_by_name(original: Product, catalog: Catalog) -> KindWords | None:
    """The original's kind words, where its name has to say what it is: it has no product type of ours, or
    its type is raw meat or fish, where the cut or the species is the product (`product_types.yaml`, `raw`).
    None for any other type: the type says the kind, and its names need not ("milk drink" and "milk")."""
    types = product_types_of(original)
    raw = any(is_raw_type(key) for key in types)
    if types and not raw:
        return None
    counts = count_category_words((original, *catalog.same_category(original.id)))
    return kind_words(original, counts, of_one_type=raw)


def _leave_out_other_products(judged: Sequence[Judged]) -> tuple[list[Judged], list[Judged]]:
    """(candidates, other products). A candidate that is another kind of product by its name is no substitute
    (decision B65): it leaves the ranking here, where the candidates are produced, so that neither the list
    nor an offer can hold it. A pair Valio lists stays: Valio's own judgement, and the reason is said.
    The allergen rule decides first, as everywhere: a candidate that fails it stays with that reason and is
    counted in the allergen note, whatever its kind."""
    others = [each for each in judged if each.passes and each.replaceable.no_shared_word and not each.listed]
    left = {id(each) for each in others}
    return [each for each in judged if id(each) not in left], others


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


def missing_listed(original: Product, catalog: Catalog) -> tuple[str, ...]:
    """The ids Valio lists as substitutes for the original that the product file does not hold."""
    return tuple(
        product_id for product_id in dict.fromkeys(catalog.listed_substitutes(original.id))
        if catalog.get_product(product_id) is None
    )


def _missing_note(missing: Sequence[str]) -> tuple[str, ...]:
    """A listed substitute that is not in the product file is said, never dropped in silence (review S12)."""
    if not missing:
        return ()
    one = len(missing) == 1
    return (
        f"{counted(len(missing), 'substitute')} Valio {'lists is' if one else 'list are'} not in the product file "
        f"and could not be judged: {', '.join(plain_name(product_id) for product_id in missing)}.",
    )


def _pool_notes(pool: Sequence[tuple[Product, bool, int]]) -> tuple[str, ...]:
    if len(pool) < MAX_POOL:
        return ()
    return (f"Only the first {MAX_POOL} candidates were checked: one price and one availability call hold no more.",)


def _judge(
    product: Product, is_listed: bool, distance: int, original: Product, need: Need, lookup: Lookup,
    catalog: Catalog, kind: KindWords | None = None,
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
        replaceable=replace_check(original, product, formula, lost, listed=is_listed, kind=kind),
        kind_said=shared_weight(kind, product) if kind is not None else 0,
    )


def replace_check(
    original: Product, other: Product, formula: FormulaCheck, lost: Sequence[str] = (), *, listed: bool = False,
    kind: KindWords | None = None,
) -> ReplaceCheck:
    """Can `other` take the original's place like for like? Type, flavour and use are read from the product
    file (`tta.catalog.kinds`, word lists ours); the formula and the dietary claims lost are given.

    Nothing the reader does not know is read as "the same" (review finding S11). Where the original has no
    product type of ours, the type cannot be judged: the sentence says so, the verdict is never plain
    "Replaceable", and a candidate whose name shares no product word with the original's is not like for like.
    Two names of one brand that differ in a word no list explains are variants of a product line: not like
    for like either, and the words are said.

    `kind`: the original's kind words (`_kind_by_name`), when the ranking measured them. A candidate whose
    name does not carry them all is another kind of product (`no_shared_word`), whatever else its name shares.
    Without them, or when the original's name has none, the older reading holds: an original with no product
    type and a candidate that shares no product word with it.
    """
    original_types, types = product_types_of(original), product_types_of(other)
    original_flavours, flavours = flavours_of(original), flavours_of(other)
    original_uses, uses = uses_of(original), uses_of(other)
    words = name_difference(original, other)
    not_said = missing_kind_words(kind, other) if kind is not None and kind.known else ()
    no_word = not not_said and not original_types and not shares_a_product_word(original, other)
    facts = ReplaceCheck(
        name_difference=words is not None,
        original_name_words=words.original_words if words is not None else (),
        name_words=words.words if words is not None else (),
        type_not_judged=not original_types,
        no_shared_word=no_word,
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
    if not_said:
        facts = facts.model_copy(update={"no_shared_word": True})
        reasons = (*reasons, kind_reason(not_said))
    if reasons:
        verdict = ReplaceVerdict.NOT_LIKE_FOR_LIKE
    elif formula.outcome is FormulaOutcome.NOT_KNOWN or facts.type_not_judged:
        # NOT_KNOWN is never read as the same formula, nor a type that was not judged as the same type.
        verdict = ReplaceVerdict.NOT_SHOWN
    else:
        verdict = ReplaceVerdict.REPLACEABLE
    same_category = original.category == other.category
    return facts.model_copy(
        update={
            "verdict": verdict,
            "reasons": reasons,
            "sentence": replace_sentence(
                facts, verdict, reasons, same_category=same_category,
                formula_known=formula.outcome is not FormulaOutcome.NOT_KNOWN,
            ),
        }
    )


def claims_not_carried(original: Product, other: Product) -> tuple[str, ...]:
    """Every nutritional claim of the original that `other` neither carries nor covers, in the original's order.

    `COVERED_BY`: a lactose-free product has not lost LOW_LACTOSE, a vegan one has not lost VEGETARIAN.
    `STATED_BY_ALLERGEN_DATA`: the allergen data is read before the label, so a product whose data says it is
    free from soybeans has not lost FREE_FROM_SOY.
    """
    carried = frozenset(other.nutritional_claims)
    return tuple(
        dict.fromkeys(
            claim
            for claim in original.nutritional_claims
            if claim not in carried
            and not COVERED_BY.get(claim, frozenset()) & carried
            and not _stated_free_from(other, claim)
        )
    )


def _stated_free_from(product: Product, claim: str) -> bool:
    """The product's own allergen data says FREE_FROM of the one allergen the claim names. The code families
    are read as everywhere (`tta.allergens.statements`): the least safe statement counts."""
    code = STATED_BY_ALLERGEN_DATA.get(claim)
    if code is None:
        return False
    return statement_for(product.allergen_statements, code) is AllergenRelation.FREE_FROM


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
    # Only the candidates that stay in the list: one of another kind keeps its claims and is held back too.
    keepers = sum(each.orderable and not _is_last_resort(each) for each in judged)
    lack = "lacks" if losers == 1 else "lack"
    are = "is" if losers == 1 else "are"
    keep = "keeps" if keepers == 1 else "keep"
    return (
        f"{counted(losers, 'candidate')} that {lack} a dietary claim of the original {are} held back as a "
        f"last resort: {keepers} that {keep} every dietary claim can be ordered.",
    )


# Each candidate held back for its kind is counted once, under the first of these that holds.
_OTHER_KIND_WORDS = (
    "flavoured where the original is not, or the reverse",
    "of another product type",
    "whose name shares no product word with the original's, which has no product type of ours",
)


def _other_kind_counts(others: Sequence[Judged]) -> tuple[int, ...]:
    counts = [0] * len(_OTHER_KIND_WORDS)
    for each in others:
        check = each.replaceable
        flags = (check.plain_against_flavoured, check.other_type, check.no_shared_word)
        counts[flags.index(True)] += 1
    return tuple(counts)


def _other_kind_note(judged: Sequence[Judged]) -> tuple[str, ...]:
    """The candidates held back for their kind alone; one that also loses a claim is counted in the claim note."""
    others = [each for each in judged if each.passes and each.other_kind and not each.claims_lost]
    if not others:
        return ()
    counts = _other_kind_counts(others)
    same = sum(each.orderable and not _is_last_resort(each) for each in judged)
    why_not = " and ".join(
        f"{count} {words}" for count, words in zip(counts, _OTHER_KIND_WORDS, strict=True) if count
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
    """Passes the allergen rules, lacks no claim of an intolerance, says most of the original's kind in its
    name (where the name is what says it), keeps every dietary claim of the original and is the same kind of
    product,
    same product type (only a pair Valio lists can differ here), same use, same flavour, formula outcome,
    listed by Valio, pack size closest to the original, verification status, price difference.

    Losing a dietary claim only orders the candidates that pass the allergen rules; it fails none of them.
    Among the last resorts the kind comes before a claim of a way of eating: a product of the same kind,
    flavour and use that lacks VEGAN or VEGETARIAN (plain fries with no VEGAN label) comes before another
    kind of product that keeps it (seasoned fries; review C3-F2). A candidate of another flavour or use is
    not put ahead this way: a plain oat drink of the brand still comes before an almond barista drink for a
    chocolate oat drink. A claim of an intolerance (gluten, wheat, lactose, eggs, soy) still comes first:
    a candidate that lacks one stays behind every candidate that keeps them all, whatever its kind (Valio,
    answer B7: "it is better to not have gluten if you are unsure").
    A claim that is not dietary does not order them at all. The formula comes after the dietary claims and
    can never lift a candidate over them: 469050 has the six figures of 469126 and is not lactose-free. The
    formula took the place of the category distance, which no longer orders anything: a pair Valio lists
    from another category is judged by what it is made of. Where the formula matters for the line, a candidate
    shown to keep it comes before the use and the flavour (`_keeper_place`), and the brand orders the
    candidates whose formula cannot be compared (`_formula_place`).
    """

    def key(each: Judged) -> tuple[object, ...]:
        candidate = each.candidate
        unconfirmed = len(unconfirmed_gating(each.claims, dated=need.dated))
        verification = (not each.orderable, unconfirmed, _shortfall(candidate, need))
        return (
            not each.passes,
            _lacks_an_intolerance_claim(each),  # the safe product first: such a candidate is a last resort
            -each.kind_said,  # then the candidate whose name says most of what the original is
            (last_resort := _is_last_resort(each)),
            last_resort and _differs_in_kind(each),  # among the last resorts, the same kind, flavour and use first
            bool(each.claims_lost),  # then one that keeps every dietary claim
            each.replaceable.other_type,
            each.replaceable.plain_against_flavoured,  # among the last resorts, after one of the same flavour
            _keeper_place(each, need.formula_matters),  # where the formula matters: the same brand and formula
            each.replaceable.other_use,
            each.replaceable.other_flavour,
            _formula_place(each, original.product, need.formula_matters),
            each.unexplained_variant,  # after the candidates of the same formula class whose names say no variant
            not each.listed,
            _pack_gap(original.pack, candidate.pack),
            verification,
            _price_gap(original, candidate),
            candidate.product.id,
        )

    return key


_NOT_SHOWN_TO_KEEP = len(FORMULA_ORDER)


def _keeper_place(each: Judged, matters: bool) -> int:
    """Where the formula matters for the line: a candidate that is shown to keep the formula comes first among
    those of the same kind, one of the original's brand before one of another brand.

    Valio Aimo's people, in person (reported by the team lead, 15 Nov 2026): where the formula and the chemistry
    are required, a product of the same brand that is known to have the same formula has priority. So there
    the formula is read before the use and the flavour a name says: the same brand's cream with the same
    contents and figures comes before a cream named for the same use whose formula differs. The kind itself
    (another product type, flavoured against plain, a name that does not say the kind) is still read first.
    Every other candidate gets one place, and is ordered as it always was. Where the formula does not matter
    every candidate gets that place: nothing moves.
    """
    if matters and each.formula.keeps_formula:
        return FORMULA_ORDER[each.formula.outcome]
    return _NOT_SHOWN_TO_KEEP


def _formula_place(each: Judged, original: Product, matters: bool) -> tuple[int, bool]:
    """Where the formula puts a candidate among those of the same kind, use and flavour, best first.

    `FORMULA_ORDER` holds the order of the candidates whose formula is shown: same brand and same formula, then
    the same formula of another brand, then a formula shown to differ. What is added where the formula matters
    (`Need.formula_matters`): among the candidates whose formula cannot be compared, one of the original's brand
    comes before one of another brand. It stays behind every candidate that is shown to keep the formula, and
    a formula shown to differ stays where it was. Where the formula does not matter the brand orders nothing
    more than before.
    """
    outcome = each.formula.outcome
    other_brand = (
        matters and outcome is FormulaOutcome.NOT_KNOWN and not same_brand(original, each.candidate.product)
    )
    return FORMULA_ORDER[outcome], other_brand


def _differs_in_kind(each: Judged) -> bool:
    """Another kind of product (`Judged.other_kind`), another flavour or another use than the original."""
    return each.other_kind or each.replaceable.other_flavour or each.replaceable.other_use


def _lacks_an_intolerance_claim(each: Judged) -> bool:
    """It lacks a dietary claim of the original that is not one of `WAY_OF_EATING_CLAIMS`."""
    return any(claim not in WAY_OF_EATING_CLAIMS for claim in each.claims_lost)


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
