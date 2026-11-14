"""Constraint checks: one per thing the buyer asked for, each MET, NOT_MET or UNVERIFIED (SPEC section 5, step 4)."""

from __future__ import annotations

from collections.abc import Sequence

from tta.availability.wording import format_day
from tta.contracts.common import (
    AllergenOutcome,
    AllergenRelation,
    AvailabilityState,
    CheckResult,
    ClaimName,
    ClaimStatus,
    ConstraintKind,
    PackPreference,
)
from tta.contracts.offer import ConstraintCheck, Coverage, OfferLine
from tta.contracts.ports import Catalog
from tta.contracts.request import MAX_PRODUCT_IDS, ProductQuery, PurchaseRequest, RequestLine
from tta.offers.candidates import Need
from tta.offers.wording import measured, plain_name

NOTHING_OFFERED = "No product is offered for this request line."
CONFIRMED_ONLY_SUBJECT = "require_confirmed"


def constraint_checks(
    request: PurchaseRequest,
    needs: Sequence[Need],
    lines: Sequence[OfferLine],
    coverage: Sequence[Coverage],
    catalog: Catalog,
) -> tuple[ConstraintCheck, ...]:
    checks: list[ConstraintCheck] = []
    for need, asked, covered in zip(needs, request.lines, coverage, strict=True):
        own = tuple(line for line in lines if line.request_line_index == need.index)
        checks.extend(_line_checks(need, asked, own, covered, catalog))
    checks.extend(_needed_by(request, needs, lines))
    checks.extend(_confirmed_only(needs, lines))
    return tuple(checks)


def _line_checks(
    need: Need, asked: RequestLine, lines: Sequence[OfferLine], covered: Coverage, catalog: Catalog
) -> list[ConstraintCheck]:
    quantity = _quantity(need, lines, covered)
    if not lines:
        not_met = CheckResult.NOT_MET
        others = [_check(need.index, kind, subject, not_met, NOTHING_OFFERED) for kind, subject in _asked(need, asked)]
        return [*others, quantity]
    return [
        *_product_type(need, asked, lines, catalog),
        *_product_ids(need, asked, lines),
        *_name_terms(need, asked, lines, catalog),
        *_claims(need, asked, lines, catalog),
        *_labels(need, asked, lines, catalog),
        quantity,
        *_pack(need, lines, catalog),
        *_allergens(need, lines),
    ]


def _check(
    index: int | None, kind: ConstraintKind, subject: str, result: CheckResult, sentence: str
) -> ConstraintCheck:
    return ConstraintCheck(request_line_index=index, kind=kind, subject=subject, result=result, sentence=sentence)


def _asked(need: Need, asked: RequestLine) -> list[tuple[ConstraintKind, str]]:
    """Everything a request line asks for besides the quantity, as (kind, subject)."""
    things: list[tuple[ConstraintKind, str]] = []
    if asked.product_type:
        things.append((ConstraintKind.PRODUCT_TYPE, asked.product_type))
    things.extend((ConstraintKind.PRODUCT_ID, product_id) for product_id in dict.fromkeys(asked.product_ids))
    things.extend((ConstraintKind.NAME_TERM, term) for term in dict.fromkeys(asked.name_terms))
    things.extend((ConstraintKind.CLAIM, claim) for claim in dict.fromkeys(asked.required_claims))
    things.extend((ConstraintKind.LABEL, label) for label in _label_codes(asked))
    if need.pack is not PackPreference.ANY:
        things.append((ConstraintKind.PACK, need.pack.value))
    things.extend((ConstraintKind.ALLERGEN, code) for code in need.excluded)
    return things


def _ids(lines: Sequence[OfferLine]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(line.product_id for line in lines))


def _matching(catalog: Catalog, lines: Sequence[OfferLine], **filters: object) -> frozenset[str]:
    """The offered products that pass one catalog filter, asked of the catalog so the rule stays in one place."""
    result = catalog.search(ProductQuery(product_ids=_ids(lines), limit=MAX_PRODUCT_IDS, **filters))
    return frozenset(product.id for product in result.products)


IDS_SLOT = "{ids}"  # where a NOT_MET sentence names the products that fail


def _all_or_named(
    need: Need, kind: ConstraintKind, subject: str, lines: Sequence[OfferLine], passing: frozenset[str], met: str,
    not_met: str,
) -> ConstraintCheck:
    failing = [product_id for product_id in _ids(lines) if product_id not in passing]
    if not failing:
        return _check(need.index, kind, subject, CheckResult.MET, met)
    # Not str.format: the sentence carries the buyer's own term, which may hold a brace.
    return _check(need.index, kind, subject, CheckResult.NOT_MET, not_met.replace(IDS_SLOT, ", ".join(failing)))


def _product_type(
    need: Need, asked: RequestLine, lines: Sequence[OfferLine], catalog: Catalog
) -> list[ConstraintCheck]:
    if not asked.product_type:
        return []
    passing = _matching(catalog, lines, product_type=asked.product_type)
    met = f"Every product offered is of the product type '{asked.product_type}'."
    not_met = f"Not of the product type '{asked.product_type}': {{ids}}."
    return [_all_or_named(need, ConstraintKind.PRODUCT_TYPE, asked.product_type, lines, passing, met, not_met)]


def _product_ids(need: Need, asked: RequestLine, lines: Sequence[OfferLine]) -> list[ConstraintCheck]:
    offered = {line.product_id: line for line in lines}
    replaced = {line.substitute.original_id: line for line in lines if line.substitute is not None}
    return [_product_id(need, product_id, offered, replaced) for product_id in dict.fromkeys(asked.product_ids)]


def _product_id(
    need: Need, product_id: str, offered: dict[str, OfferLine], replaced: dict[str, OfferLine]
) -> ConstraintCheck:
    kind = ConstraintKind.PRODUCT_ID
    if product_id in replaced:
        stand_in = f"{plain_name(replaced[product_id].name)} ({replaced[product_id].product_id})"
        part = "part of " if product_id in offered else ""
        sentence = f"{stand_in} is offered in place of {part}product {product_id}."
        return _check(need.index, kind, product_id, CheckResult.NOT_MET, sentence)
    if product_id in offered:
        return _check(need.index, kind, product_id, CheckResult.MET, f"Product {product_id} is offered as asked.")
    sentence = f"Product {product_id} is not part of this option."
    return _check(need.index, kind, product_id, CheckResult.NOT_MET, sentence)


def _name_terms(need: Need, asked: RequestLine, lines: Sequence[OfferLine], catalog: Catalog) -> list[ConstraintCheck]:
    checks = []
    for term in dict.fromkeys(asked.name_terms):
        passing = _matching(catalog, lines, name_terms=(term,))
        met = f"The name of every product offered contains '{term}'."
        not_met = f"'{term}' is not in the name of: {{ids}}."
        checks.append(_all_or_named(need, ConstraintKind.NAME_TERM, term, lines, passing, met, not_met))
    return checks


def _claims(need: Need, asked: RequestLine, lines: Sequence[OfferLine], catalog: Catalog) -> list[ConstraintCheck]:
    checks = []
    for claim in dict.fromkeys(asked.required_claims):
        passing = _matching(catalog, lines, required_claims=(claim,))
        # A nutritional claim is never an allergen statement (AIMO/docs/SCHEMA-AND-CODES.md section 4).
        met = f"Every product offered carries the nutritional claim {claim}. A claim is not an allergen statement."
        not_met = f"Without the nutritional claim {claim}: {{ids}}."
        checks.append(_all_or_named(need, ConstraintKind.CLAIM, claim, lines, passing, met, not_met))
    return checks


def _labels(need: Need, asked: RequestLine, lines: Sequence[OfferLine], catalog: Catalog) -> list[ConstraintCheck]:
    """One check per certificate label, asked of the catalog as the claims are (task SUST-1)."""
    checks = []
    for label in _label_codes(asked):
        passing = _matching(catalog, lines, required_labels=(label,))
        met = f"Every product offered carries the certificate label {label}."
        # The label is the caller's text: braces in it must not reach `str.format` in `_all_or_named`.
        literal = label.replace("{", "{{").replace("}", "}}")
        not_met = f"Without the certificate label {literal}: {{ids}}."
        checks.append(_all_or_named(need, ConstraintKind.LABEL, label, lines, passing, met, not_met))
    return checks


def _label_codes(asked: RequestLine) -> tuple[str, ...]:
    """The labels as the catalog search reads them: trimmed, in capitals, each once."""
    return tuple(dict.fromkeys(label.strip().upper() for label in asked.required_labels if label.strip()))


def _quantity(need: Need, lines: Sequence[OfferLine], covered: Coverage) -> ConstraintCheck:
    asked = measured(covered.requested, covered.unit)
    kind = ConstraintKind.QUANTITY
    if covered.missing > 0:
        short = f"{measured(covered.covered, covered.unit)} of the {asked} asked for are covered; "
        sentence = f"{short}{measured(covered.missing, covered.unit)} are missing."
        return _check(need.index, kind, asked, CheckResult.NOT_MET, sentence)
    if any(line.availability.state is not AvailabilityState.CONFIRMED for line in lines):
        sentence = f"The {asked} asked for are offered, but Valio does not confirm the quantity in stock."
        return _check(need.index, kind, asked, CheckResult.UNVERIFIED, sentence)
    return _check(need.index, kind, asked, CheckResult.MET, f"The {asked} asked for are covered by confirmed stock.")


def _pack(need: Need, lines: Sequence[OfferLine], catalog: Catalog) -> list[ConstraintCheck]:
    if need.pack is PackPreference.ANY:
        return []
    wants_portions = need.pack is PackPreference.PORTION
    wrong = [
        line.product_id for line in lines if _is_portion_pack(catalog, line.product_id) is not wants_portions
    ]
    wanted = "a pack of single-serve portions" if wants_portions else "a bulk pack, not single-serve portions"
    if wrong:
        sentence = f"Not {wanted}: {', '.join(dict.fromkeys(wrong))}."
        return [_check(need.index, ConstraintKind.PACK, need.pack.value, CheckResult.NOT_MET, sentence)]
    sentence = f"Every product offered is {wanted}."
    return [_check(need.index, ConstraintKind.PACK, need.pack.value, CheckResult.MET, sentence)]


def _is_portion_pack(catalog: Catalog, product_id: str) -> bool:
    product = catalog.get_product(product_id)
    return product is not None and catalog.is_portion_pack(product)


def _allergens(need: Need, lines: Sequence[OfferLine]) -> list[ConstraintCheck]:
    return [_allergen(need, code, lines) for code in need.excluded]


def _allergen(need: Need, code: str, lines: Sequence[OfferLine]) -> ConstraintCheck:
    findings = [
        finding
        for line in lines
        if line.allergen_check is not None
        for finding in line.allergen_check.findings
        if finding.excluded_code == code
    ]
    kind = ConstraintKind.ALLERGEN
    rejected = [finding for finding in findings if finding.outcome is AllergenOutcome.REJECT]
    if rejected:
        return _check(need.index, kind, code, CheckResult.NOT_MET, rejected[0].sentence)
    stated_free = len(findings) == len(lines) and all(
        finding.relation is AllergenRelation.FREE_FROM for finding in findings
    )
    if stated_free:
        sentence = f"Every product offered states that it is free from {code}."
        return _check(need.index, kind, code, CheckResult.MET, sentence)
    open_findings = (finding.sentence for finding in findings if finding.relation is not AllergenRelation.FREE_FROM)
    unsettled = next(open_findings, "")
    sentence = f"The product data does not confirm that every product offered is free from {code}. {unsettled}".strip()
    return _check(need.index, kind, code, CheckResult.UNVERIFIED, sentence)


def _needed_by(request: PurchaseRequest, needs: Sequence[Need], lines: Sequence[OfferLine]) -> list[ConstraintCheck]:
    """Only for a dated request. MET only when every request line has a product offered and every line's
    delivery-date claim is confirmed."""
    if request.needed_by is None:
        return []
    day = format_day(request.needed_by)
    empty = _empty_lines(needs, lines)
    statuses = [_status(line, ClaimName.DELIVERY_DATE) for line in lines]
    if empty:
        sentence = f"Nothing is offered for {_lines_label(empty)}, so the request is not delivered in full by {day}."
        result = CheckResult.NOT_MET
    elif any(status is ClaimStatus.RULED_OUT for status in statuses):
        result, sentence = CheckResult.NOT_MET, f"A product offered cannot be delivered by {day}."
    elif all(status is ClaimStatus.CONFIRMED for status in statuses):
        result, sentence = CheckResult.MET, f"Every product offered is delivered by {day} if ordered by its cut-off."
    else:
        result, sentence = CheckResult.UNVERIFIED, f"Valio's data does not confirm delivery by {day} for every product."
    return [_check(None, ConstraintKind.NEEDED_BY, request.needed_by.isoformat(), result, sentence)]


def _confirmed_only(needs: Sequence[Need], lines: Sequence[OfferLine]) -> list[ConstraintCheck]:
    if not any(need.require_confirmed for need in needs):
        return []
    dated = any(need.dated for need in needs)
    kind = ConstraintKind.CONFIRMED_ONLY
    empty = _empty_lines(needs, lines)
    if empty:
        sentence = f"Nothing is offered for {_lines_label(empty)}, so the request is not covered by confirmed data."
        return [_check(None, kind, CONFIRMED_ONLY_SUBJECT, CheckResult.NOT_MET, sentence)]
    if all(line.confirmed_for_order(dated=dated) for line in lines):
        sentence = "Every claim an order depends on is confirmed by Valio's data for every product offered."
        return [_check(None, kind, CONFIRMED_ONLY_SUBJECT, CheckResult.MET, sentence)]
    sentence = "A claim an order depends on is not confirmed for a product offered."
    return [_check(None, kind, CONFIRMED_ONLY_SUBJECT, CheckResult.NOT_MET, sentence)]


def _empty_lines(needs: Sequence[Need], lines: Sequence[OfferLine]) -> tuple[int, ...]:
    """The request lines no product is offered for. A check over "every product offered" says nothing
    about them, so it cannot be met while one exists."""
    offered = {line.request_line_index for line in lines}
    return tuple(need.index for need in needs if need.index not in offered)


def _lines_label(indexes: Sequence[int]) -> str:
    """`request line 2`, `request lines 2 and 3`, `request lines 2, 3 and 5`."""
    numbers = [str(index + 1) for index in indexes]
    if len(numbers) == 1:
        return f"request line {numbers[0]}"
    return f"request lines {', '.join(numbers[:-1])} and {numbers[-1]}"


def _status(line: OfferLine, claim: ClaimName) -> ClaimStatus | None:
    return next((check.status for check in line.claims if check.claim is claim), None)
