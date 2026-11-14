"""Verification status per claim: our answer to the trust protocol (SPEC section 4).

For each claim of an offer line (price, quantity, delivery date, allergens, origin) this says
whether Valio's data confirms it, leaves it unknown or rules it out, with one sentence.
Pure functions: the clock is an argument and nothing is looked up.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal

from tta.availability.states import classify, late_sentence
from tta.availability.wording import (
    format_amount,
    format_day,
    format_moment,
    format_price,
    format_validity,
    is_open_ended,
)
from tta.contracts.allergen import AllergenCheck, AllergenFinding
from tta.contracts.availability import AvailabilityAssessment, AvailabilityLine, ClaimCheck, PriceLine
from tta.contracts.common import (
    AllergenOutcome,
    AllergenRelation,
    AvailabilityState,
    ClaimName,
    ClaimStatus,
)
from tta.contracts.product import Product

# `zy`, `xs` and `zz` are not ISO 3166-1 codes: the product file uses them as placeholders
# (AIMO/docs/PRODUCT-DATA.md, "countryOfOrigin"). A placeholder does not state an origin.
ORIGIN_PLACEHOLDERS = frozenset({"zy", "xs", "zz"})
# Relations that leave an excluded allergen open (SPEC section 4, row "allergens", column UNKNOWN).
UNSETTLED_RELATIONS = frozenset(
    {AllergenRelation.MAY_CONTAIN, AllergenRelation.UNDECLARED, AllergenRelation.NOT_STATED}
)


def verify(
    line: AvailabilityLine,
    price: PriceLine | None,
    product: Product,
    *,
    quantity: Decimal | None,
    needed_by: date | None,
    allergen_outcome: AllergenCheck | None,
    now: datetime,
) -> tuple[ClaimCheck, ...]:
    """The status of each claim, in the order price, quantity, delivery date, allergens, origin.

    `quantity` is the quantity of the offer line in sales units (`None`: no quantity was asked).
    `allergen_outcome` is the result of the buyer exclusion rule (`None`: the buyer excluded nothing).
    """
    assessment = classify(line, now)
    return (
        _price_claim(price, assessment.sales_unit, now),
        _quantity_claim(assessment, quantity),
        _delivery_date_claim(assessment, needed_by),
        _allergens_claim(allergen_outcome),
        _origin_claim(product),
    )


def _check(claim: ClaimName, status: ClaimStatus, sentence: str) -> ClaimCheck:
    return ClaimCheck(claim=claim, status=status, sentence=sentence)


def _price_claim(price: PriceLine | None, sales_unit: str | None, now: datetime) -> ClaimCheck:
    amount = price.catalog_price if price is not None and price.has_price else None
    if amount is None:
        return _check(ClaimName.PRICE, ClaimStatus.UNKNOWN, "Valio returned no price for this product.")
    figure, until = format_price(amount), format_validity(amount.valid_to)
    if amount.valid_to <= now:
        sentence = f"Valio's price of {figure} was valid until {until}, which has passed."
        return _check(ClaimName.PRICE, ClaimStatus.UNKNOWN, sentence)
    validity = "with no end date" if is_open_ended(amount.valid_to) else f"valid until {until}"
    # The price is per sales unit of the API line, not of the product file (AIMO/FINDINGS.md section 1).
    sentence = f"Valio's price is {figure} per {sales_unit or 'sales unit'} before tax, {validity}."
    return _check(ClaimName.PRICE, ClaimStatus.CONFIRMED, sentence)


def _quantity_claim(assessment: AvailabilityAssessment, quantity: Decimal | None) -> ClaimCheck:
    if assessment.state is AvailabilityState.QUANTITY_NOT_CONFIRMED:
        return _check(ClaimName.QUANTITY, ClaimStatus.UNKNOWN, assessment.sentence)
    if assessment.state is AvailabilityState.CUTOFF_PASSED:
        sentence = "The order cut-off has passed, so no quantity is confirmed for a later delivery."
        return _check(ClaimName.QUANTITY, ClaimStatus.UNKNOWN, sentence)
    if assessment.usable_amount is None:  # blocked, not deliverable or out of stock
        return _check(ClaimName.QUANTITY, ClaimStatus.RULED_OUT, assessment.sentence)
    stock = f"Valio shows {format_amount(assessment.usable_amount)} {assessment.sales_unit} in stock"
    if quantity is None:
        return _check(ClaimName.QUANTITY, ClaimStatus.CONFIRMED, f"{stock}.")
    asked = f"the {format_amount(quantity)} {assessment.sales_unit} of this line"
    if assessment.usable_amount < quantity:
        return _check(ClaimName.QUANTITY, ClaimStatus.RULED_OUT, f"{stock}, fewer than {asked}.")
    return _check(ClaimName.QUANTITY, ClaimStatus.CONFIRMED, f"{stock}, enough for {asked}.")


def _delivery_date_claim(assessment: AvailabilityAssessment, needed_by: date | None) -> ClaimCheck:
    if not assessment.is_orderable_state:  # blocked, not deliverable, out of stock or cut-off passed
        return _check(ClaimName.DELIVERY_DATE, ClaimStatus.RULED_OUT, assessment.sentence)
    available_date, cutoff = assessment.available_date, assessment.closing_time
    if available_date is None:
        return _check(ClaimName.DELIVERY_DATE, ClaimStatus.UNKNOWN, "Valio gave no delivery date for this product.")
    if needed_by is not None and available_date > needed_by:
        return _check(ClaimName.DELIVERY_DATE, ClaimStatus.RULED_OUT, late_sentence(available_date, needed_by))
    day = format_day(available_date)
    if cutoff is None:
        sentence = f"Valio gave no order cut-off, so delivery on {day} cannot be confirmed."
        return _check(ClaimName.DELIVERY_DATE, ClaimStatus.UNKNOWN, sentence)
    terms = f"if ordered by {format_moment(cutoff)}"
    if needed_by is None:
        sentence = f"No needed-by date was given; Valio shows delivery on {day} {terms}."
        return _check(ClaimName.DELIVERY_DATE, ClaimStatus.UNKNOWN, sentence)
    sentence = f"Delivery on {day} meets the needed-by date {format_day(needed_by)} {terms}."
    return _check(ClaimName.DELIVERY_DATE, ClaimStatus.CONFIRMED, sentence)


def _allergens_claim(check: AllergenCheck | None) -> ClaimCheck:
    """Reads the outcome of the buyer exclusion rule; the rule itself lives in `tta.allergens`."""
    if check is None or (not check.findings and check.outcome is AllergenOutcome.PASS):
        sentence = "The buyer excluded no allergen, so there is nothing to check."
        return _check(ClaimName.ALLERGENS, ClaimStatus.CONFIRMED, sentence)
    if check.declares_excluded or check.outcome is AllergenOutcome.REJECT:
        declared = _codes(finding for finding in check.findings if finding.outcome is AllergenOutcome.REJECT)
        sentence = f"The product declares that it contains an excluded allergen{declared}."
        return _check(ClaimName.ALLERGENS, ClaimStatus.RULED_OUT, sentence)
    if check.all_explicit and check.outcome is AllergenOutcome.PASS:
        sentence = f"The product states that it is free from every excluded allergen{_codes(check.findings)}."
        return _check(ClaimName.ALLERGENS, ClaimStatus.CONFIRMED, sentence)
    unsettled = _codes(
        finding for finding in check.findings
        if finding.outcome is AllergenOutcome.TO_HUMAN or finding.relation in UNSETTLED_RELATIONS
    )
    sentence = f"The product data does not confirm that it is free from an excluded allergen{unsettled}."
    return _check(ClaimName.ALLERGENS, ClaimStatus.UNKNOWN, sentence)


def _codes(findings: Iterable[AllergenFinding]) -> str:
    """` (AM, AW)`: the excluded codes of the findings, each once, in their order; empty when there is none."""
    codes = tuple(dict.fromkeys(finding.excluded_code for finding in findings))
    return f" ({', '.join(codes)})" if codes else ""


def _origin_claim(product: Product) -> ClaimCheck:
    code = (product.country_of_origin or "").strip().lower()
    if code and code not in ORIGIN_PLACEHOLDERS:
        sentence = f"The product file states the country of origin: {code.upper()}."
        return _check(ClaimName.ORIGIN, ClaimStatus.CONFIRMED, sentence)
    if product.countries_of_origin:
        numeric = ", ".join(product.countries_of_origin)
        sentence = f"The product file states the country of origin by ISO 3166-1 numeric code: {numeric}."
        return _check(ClaimName.ORIGIN, ClaimStatus.CONFIRMED, sentence)
    return _check(ClaimName.ORIGIN, ClaimStatus.UNKNOWN, "The product file does not state a country of origin.")
