"""From a request line to judged candidates (SPEC section 3, and section 5 steps 1 and 2).

A candidate either fits or drops out with one reason code and one sentence. The checks run in a fixed
order: first what does not match the request (allergens, pack), then, in replay, a product the recorded
copy holds no answer for, then what Valio cannot supply now (availability state, delivery date, price), so
the reason a buyer reads is the most lasting one. Last come the checks that apply only when confirmed data
only was asked for.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from tta.allergens import check_exclusions
from tta.availability import classify, is_late, late_sentence, verify
from tta.availability.wording import format_amount, format_validity
from tta.contracts.allergen import AllergenCheck
from tta.contracts.availability import AvailabilityAssessment, AvailabilityLine, ClaimCheck, PriceLine
from tta.contracts.common import (
    CURRENCY_EUR,
    AllergenOutcome,
    AllergenRelation,
    AllergenStrictness,
    AvailabilityState,
    ClaimName,
    ClaimStatus,
    ExclusionReason,
    PackPreference,
    PackSizeSource,
    Unit,
)
from tta.contracts.errors import InvalidRequest, UnknownProduct
from tta.contracts.policy import BuyerProfile
from tta.contracts.ports import Catalog
from tta.contracts.product import PackSize, Product
from tta.contracts.request import MAX_PRODUCT_IDS, ProductQuery, PurchaseRequest, RequestLine
from tta.offers.combining import ceil_to_step
from tta.offers.deps import Lookup
from tta.offers.wording import UNIT_WORDS, eur

# Below every lot step of the catalog (the smallest is 0.01, AIMO/FINDINGS.md section 4), so rounding
# it up to the lot gives the step itself. The `Catalog` port has no method that names the step.
SMALLEST_QUANTITY = Decimal("0.001")
ONE_SALES_UNIT = Decimal(1)
# Claims that gate an order without a human (SPEC section 4); the delivery date only for a dated request.
GATING_CLAIMS = (ClaimName.PRICE, ClaimName.QUANTITY, ClaimName.ALLERGENS)

_STRICTNESS_RANK = {AllergenStrictness.DECLARED_ONLY: 0, AllergenStrictness.STRICT: 1}
_STATE_REASONS = {
    AvailabilityState.BLOCKED: ExclusionReason.BLOCKED,
    AvailabilityState.NOT_DELIVERABLE: ExclusionReason.NOT_DELIVERABLE,
    AvailabilityState.OUT_OF_STOCK: ExclusionReason.OUT_OF_STOCK,
    AvailabilityState.CUTOFF_PASSED: ExclusionReason.CUTOFF_PASSED,
}
CONFIRMED_ONLY_ASKED = "Confirmed data only was asked for."
# Replay only: the recorded copy has no answer for the product. Never worded as something Valio said (SPEC 5).
NOT_IN_RECORDING_SENTENCE = "Not in the recorded copy of Valio's data used for this demo; a live lookup would answer."
# Under confirmed-only, the reason for a claim an order depends on that Valio's data does not confirm
# (SPEC section 5, "Exclusion reason codes").
_UNCONFIRMED_REASONS = {
    ClaimName.PRICE: ExclusionReason.PRICE_UNAVAILABLE,
    ClaimName.QUANTITY: ExclusionReason.QUANTITY_NOT_CONFIRMED,
    ClaimName.ALLERGENS: ExclusionReason.ALLERGEN_NOT_STATED,
    ClaimName.DELIVERY_DATE: ExclusionReason.DELIVERY_DATE_NOT_CONFIRMED,
}

Dropped = tuple[ExclusionReason, str]


@dataclass(frozen=True)
class Need:
    """What is asked of a product, with the buyer profile's rules folded in."""

    index: int  # the request line
    quantity: Decimal | None  # None only for a substitute query that gives no quantity
    unit: Unit
    pack: PackPreference
    excluded: tuple[str, ...]  # the profile's allergen exclusions plus the request line's
    strictness: AllergenStrictness | None
    needed_by: date | None
    require_confirmed: bool

    @property
    def dated(self) -> bool:
        return self.needed_by is not None


@dataclass(frozen=True)
class Candidate:
    """One product with what Valio says about it now and what the buyer's allergen rule says."""

    product: Product
    price: PriceLine | None
    line: AvailabilityLine
    assessment: AvailabilityAssessment
    pack: PackSize
    per_unit: Decimal | None  # how much of the request's unit one sales unit holds; None: not known
    lot_step: Decimal
    is_portion_pack: bool
    allergen_check: AllergenCheck | None  # None: the buyer excluded nothing

    @property
    def state(self) -> AvailabilityState:
        return self.assessment.state

    @property
    def not_in_recording(self) -> bool:
        """Replay only: the recorded copy holds no price or no availability answer for this product."""
        return self.line.not_in_recording or (self.price is not None and self.price.not_in_recording)

    @property
    def unit_price(self) -> Decimal:
        """Net price per sales unit. Read only after `price_problem` found none."""
        if self.price is None or self.price.catalog_price is None:
            raise ValueError(f"product {self.product.id} has no price")
        return self.price.catalog_price.value

    @property
    def sales_unit(self) -> str:
        # Price and quantity follow the sales unit on the API line, not the product file's (SPEC section 3, step 7).
        return self.assessment.sales_unit or self.product.sales_unit


@dataclass(frozen=True)
class Found:
    """The candidate products of one request line, and what the search has to say."""

    products: tuple[Product, ...]
    note: str | None = None


def need_for(index: int, line: RequestLine, request: PurchaseRequest, profile: BuyerProfile) -> Need:
    """Raises `InvalidRequest` for an unknown allergen code and for an exclusion with no strictness."""
    excluded = tuple(dict.fromkeys((*profile.excluded_allergens, *line.exclude_allergens)))
    strictness = _strictest(profile.allergen_strictness, line.allergen_strictness) if excluded else None
    check_exclusions((), excluded, strictness)  # validates the codes and the strictness once, before any product
    return Need(
        index=index,
        quantity=line.quantity,
        unit=line.unit,
        pack=line.pack,
        excluded=excluded,
        strictness=strictness,
        needed_by=request.needed_by,
        # Confirmed data only when the request asks for it or the buyer profile sets it (SPEC section 7).
        require_confirmed=request.require_confirmed or profile.require_confirmed,
    )


def find_products(line: RequestLine, catalog: Catalog) -> Found:
    """SPEC section 3, steps 1 to 4. Raises `UnknownProduct` for a named id the catalog does not hold."""
    if line.product_type is not None and line.product_type not in catalog.product_type_keys():
        known = ", ".join(catalog.product_type_keys())
        raise InvalidRequest(f"Unknown product type. The product types are: {known}.")
    if line.product_ids:
        return Found(tuple(named_product(catalog, product_id) for product_id in dict.fromkeys(line.product_ids)))
    query = ProductQuery(
        product_type=line.product_type, name_terms=line.name_terms, required_claims=line.required_claims,
        limit=MAX_PRODUCT_IDS,
    )
    result = catalog.search(query)
    products = tuple(product for product in result.products if not product.deleted)
    if not products:
        return Found((), result.note or "No product matches.")
    if result.total > len(result.products):
        return Found(products, f"Only the first {len(products)} of {result.total} matching products were checked.")
    return Found(products)


def named_product(catalog: Catalog, product_id: str) -> Product:
    """A product asked for by id. A deleted product is treated as unknown.

    The error does not repeat the id: it is the caller's own text, and a problem body is no place to
    echo it back.
    """
    product = catalog.get_product(product_id)
    if product is None or product.deleted:
        raise UnknownProduct("A product id of the request is not in the catalog.")
    return product


def evaluate(product: Product, need: Need, lookup: Lookup, catalog: Catalog) -> Candidate:
    price = lookup.price(product.id)
    line = lookup.line(product.id)
    assessment = classify(line, lookup.now)
    if line.not_in_recording:
        # The made-up line has the shape of "cannot be delivered on any date", which Valio never said here.
        assessment = assessment.model_copy(update={"sentence": NOT_IN_RECORDING_SENTENCE})
    pack = _pack_size(product, price, assessment.sales_unit, need.unit, catalog)
    check = None
    if need.excluded:
        # The product's own ingredient list counts as a statement (SPEC section 6).
        check = check_exclusions(
            product.allergen_statements, need.excluded, need.strictness, ingredients=product.key_ingredients
        )
    return Candidate(
        product=product,
        price=price,
        line=line,
        assessment=assessment,
        pack=pack,
        per_unit=_per_unit(pack, need.unit),
        lot_step=catalog.round_to_lot(product, SMALLEST_QUANTITY),
        is_portion_pack=catalog.is_portion_pack(product),
        allergen_check=check,
    )


def exclusion_for(candidate: Candidate, need: Need, now: datetime) -> Dropped | None:
    """The first reason the candidate drops out, with its sentence; `None` when it fits."""
    for check in _CHECKS:
        dropped = check(candidate, need, now)
        if dropped is not None:
            return dropped
    return None


def price_problem(price: PriceLine | None, now: datetime) -> str | None:
    """Why the price cannot carry an offer, as one sentence; `None` when it can."""
    amount = price.catalog_price if price is not None and price.has_price else None
    if amount is None:
        return "Valio returned no price for this product."
    if amount.currency != CURRENCY_EUR:
        return f"Valio's price is in {amount.currency}, not in EUR, so it cannot be offered."
    if amount.value <= 0:
        return f"Valio's net price is {eur(amount.value)}, which is not a price an order can rest on."
    if amount.valid_from > now:
        return f"Valio's price is valid only from {format_validity(amount.valid_from)}."
    if amount.valid_to <= now:
        return f"Valio's price was valid until {format_validity(amount.valid_to)}, which has passed."
    return None


def units_needed(candidate: Candidate, quantity: Decimal) -> Decimal:
    """Sales units that cover `quantity` of the request's unit, rounded up to the lot step."""
    if candidate.per_unit is None:
        raise ValueError(f"the pack size of product {candidate.product.id} is not known")
    return ceil_to_step(quantity / candidate.per_unit, candidate.lot_step)


def claims_of(candidate: Candidate, need: Need, units: Decimal | None, now: datetime) -> tuple[ClaimCheck, ...]:
    """The five claims of SPEC section 4, in order, for `units` sales units; one the recording cannot answer is
    unknown, with the sentence that says so."""
    claims = verify(
        candidate.line, candidate.price, candidate.product, quantity=units, needed_by=need.needed_by,
        allergen_outcome=candidate.allergen_check, now=now,
    )
    unrecorded = _unrecorded_claims(candidate)
    return tuple(
        ClaimCheck(claim=check.claim, status=ClaimStatus.UNKNOWN, sentence=NOT_IN_RECORDING_SENTENCE)
        if check.claim in unrecorded else check
        for check in claims
    )


def _unrecorded_claims(candidate: Candidate) -> frozenset[ClaimName]:
    """The claims the recorded copy cannot answer: price without a recorded price, quantity and delivery date
    without a recorded availability. Allergens and origin come from the product file."""
    claims: set[ClaimName] = set()
    if candidate.price is not None and candidate.price.not_in_recording:
        claims.add(ClaimName.PRICE)
    if candidate.line.not_in_recording:
        claims.update((ClaimName.QUANTITY, ClaimName.DELIVERY_DATE))
    return frozenset(claims)


def unconfirmed_gating(claims: tuple[ClaimCheck, ...], *, dated: bool) -> tuple[ClaimName, ...]:
    """The claims an order depends on that are not confirmed (SPEC section 4, "Which claims gate")."""
    gating = (*GATING_CLAIMS, ClaimName.DELIVERY_DATE) if dated else GATING_CLAIMS
    status = {check.claim: check.status for check in claims}
    return tuple(claim for claim in gating if status.get(claim) is not ClaimStatus.CONFIRMED)


def _strictest(first: AllergenStrictness | None, second: AllergenStrictness | None) -> AllergenStrictness | None:
    """A request can add to the profile's allergen rule and never weaken it (SPEC section 3)."""
    given = [strictness for strictness in (first, second) if strictness is not None]
    return max(given, key=_STRICTNESS_RANK.__getitem__, default=None)


def _pack_size(
    product: Product, price: PriceLine | None, api_unit: str | None, unit: Unit, catalog: Catalog
) -> PackSize:
    pack = catalog.pack_size(product, price, unit)
    # The API prices another sales unit than the product file on some lines (AIMO/FINDINGS.md section 1).
    # The price ratio follows the API's unit; a size read from the file describes the file's unit.
    describes_another_unit = api_unit is not None and api_unit != product.sales_unit
    if describes_another_unit and pack.source is not PackSizeSource.PRICE_RATIO:
        return PackSize()
    return pack


def _per_unit(pack: PackSize, unit: Unit) -> Decimal | None:
    if unit is Unit.UNIT:
        return ONE_SALES_UNIT
    if pack.is_known and pack.unit is unit and pack.value is not None and pack.value > 0:
        return pack.value
    return None


def _allergen_declared(candidate: Candidate, _need: Need, _now: datetime) -> Dropped | None:
    check = candidate.allergen_check
    if check is None or not (check.declares_excluded or check.outcome is AllergenOutcome.REJECT):
        return None
    sentences = [finding.sentence for finding in check.findings if finding.outcome is AllergenOutcome.REJECT]
    return ExclusionReason.ALLERGEN_DECLARED, " ".join(sentences) or "The product declares an excluded allergen."


def _pack_preference(candidate: Candidate, need: Need, _now: datetime) -> Dropped | None:
    if need.pack is PackPreference.BULK and candidate.is_portion_pack:
        return ExclusionReason.PORTION_PACK, f"{_portion_fact(candidate.pack)} The request is for bulk packs."
    if need.pack is PackPreference.PORTION and not candidate.is_portion_pack:
        sentence = "This is not a pack of single-serve portions, and the request is for portion packs."
        return ExclusionReason.NOT_A_PORTION_PACK, sentence
    return None


def _portion_fact(pack: PackSize) -> str:
    if pack.inner_units is None or pack.inner_unit_size is None or pack.unit is None:
        return "This is a pack of single-serve portions."
    size = f"{format_amount(pack.inner_unit_size)} {UNIT_WORDS[pack.unit]}"
    return f"This is a pack of single-serve portions: one sales unit holds {pack.inner_units} portions of {size}."


def _not_in_recording(candidate: Candidate, _need: Need, _now: datetime) -> Dropped | None:
    """Replay only. After the facts of the product file (allergens, pack) and before everything that needs
    Valio's answer: the pack size can rest on the price, and the state on the availability line."""
    return (ExclusionReason.NOT_IN_RECORDING, NOT_IN_RECORDING_SENTENCE) if candidate.not_in_recording else None


def _pack_size_unknown(candidate: Candidate, need: Need, _now: datetime) -> Dropped | None:
    if candidate.per_unit is not None:
        return None
    measure = UNIT_WORDS[need.unit]
    sentence = (
        f"How many {measure} one sales unit holds is not known from the price or the product file, "
        f"so a quantity in {measure} cannot be worked out."
    )
    return ExclusionReason.PACK_SIZE_UNKNOWN, sentence


def _state(candidate: Candidate, _need: Need, _now: datetime) -> Dropped | None:
    reason = _STATE_REASONS.get(candidate.state)
    return (reason, candidate.assessment.sentence) if reason is not None else None


def _late(candidate: Candidate, need: Need, _now: datetime) -> Dropped | None:
    available_date = candidate.assessment.available_date
    if need.needed_by is None or available_date is None or not is_late(candidate.line, need.needed_by):
        return None
    return ExclusionReason.LATE_FOR_NEEDED_BY, late_sentence(available_date, need.needed_by)


def _price(candidate: Candidate, _need: Need, now: datetime) -> Dropped | None:
    problem = price_problem(candidate.price, now)
    return (ExclusionReason.PRICE_UNAVAILABLE, problem) if problem is not None else None


def _allergen_not_stated(candidate: Candidate, need: Need, _now: datetime) -> Dropped | None:
    """Only under confirmed-only: an excluded allergen the product data does not settle (SPEC section 5)."""
    check = candidate.allergen_check
    if not need.require_confirmed or check is None or not check.findings:
        return None
    if check.all_explicit and check.outcome is AllergenOutcome.PASS:
        return None
    unsettled = [finding.sentence for finding in check.findings if finding.relation is not AllergenRelation.FREE_FROM]
    return ExclusionReason.ALLERGEN_NOT_STATED, " ".join([CONFIRMED_ONLY_ASKED, *unsettled])


def _not_confirmed(candidate: Candidate, need: Need, now: datetime) -> Dropped | None:
    """Only under confirmed-only: the first claim an order depends on that Valio's data does not confirm.

    The checks before this one catch a price that cannot be used and an allergen that is not settled, so
    what is left is a quantity or, for a dated request, a delivery date that is not confirmed. A product
    that passes is confirmed for order; none is left out later without a reason.
    """
    if not need.require_confirmed:
        return None
    claims = claims_of(candidate, need, None, now)
    unconfirmed = unconfirmed_gating(claims, dated=need.dated)
    if not unconfirmed:
        return None
    sentences = {check.claim: check.sentence for check in claims}
    return _UNCONFIRMED_REASONS[unconfirmed[0]], f"{CONFIRMED_ONLY_ASKED} {sentences.get(unconfirmed[0], '')}".strip()


_CHECKS: tuple[Callable[[Candidate, Need, datetime], Dropped | None], ...] = (
    _allergen_declared,
    _pack_preference,
    _not_in_recording,
    _pack_size_unknown,
    _state,
    _late,
    _price,
    _allergen_not_stated,
    _not_confirmed,
)
