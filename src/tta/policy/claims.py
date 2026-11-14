"""What an offer option states about the claims that gate an order (SPEC section 4, "Which claims gate").

The statuses are read as the offer carries them: the availability package wrote them and nothing is worked
out again here. A claim stated more than once counts as its least favourable statement. A claim that is
not stated at all is reported as absent (`None`); the caller turns that into a missing fact, never a pass.
"""

from __future__ import annotations

from collections.abc import Mapping

from tta.contracts.common import CheckResult, ClaimName, ClaimStatus, ConstraintKind
from tta.contracts.offer import ConstraintCheck, OfferLine, OfferOption
from tta.policy.text import unique

# Most to least favourable: the statement furthest down counts.
_CLAIM_STATUSES = (ClaimStatus.CONFIRMED, ClaimStatus.UNKNOWN, ClaimStatus.RULED_OUT)
_CHECK_RESULTS = (CheckResult.MET, CheckResult.UNVERIFIED, CheckResult.NOT_MET)

# The value of the fact `option.needed_by_check` when the option carries no needed-by check: the request
# gave no date, so there is none to meet (SPEC section 4).
NEEDED_BY_NOT_ASKED = "NOT_ASKED"
# The claims the policy reads, as they are named in a sentence. Allergens gate through the allergen rule
# (F-02, P-04) and origin never gates, so neither is read here.
CLAIM_WORDS: Mapping[ClaimName, str] = {
    ClaimName.PRICE: "price",
    ClaimName.QUANTITY: "quantity",
    ClaimName.DELIVERY_DATE: "delivery-date",
}
PRICE_NOT_CONFIRMED = "the price is not confirmed by Valio Aimo"
DELIVERY_DATE_RULED_OUT = "the delivery date is ruled out"
NEEDED_BY_WORDS: Mapping[CheckResult, str] = {
    CheckResult.NOT_MET: "is not met",
    CheckResult.UNVERIFIED: "cannot be verified",
}


def claim_status(line: OfferLine, claim: ClaimName) -> ClaimStatus | None:
    """The status of one claim of a line; `None` when the line does not carry the claim."""
    statuses = [check.status for check in line.claims if check.claim is claim]
    return max(statuses, key=_CLAIM_STATUSES.index, default=None)


def unconfirmed_reasons(line: OfferLine) -> tuple[str, ...]:
    """Why rule F-07 holds for a line, one clause per reason; empty when it does not."""
    reasons: list[str] = []
    price = claim_status(line, ClaimName.PRICE)
    if price is not None and price is not ClaimStatus.CONFIRMED:
        reasons.append(PRICE_NOT_CONFIRMED)
    if claim_status(line, ClaimName.DELIVERY_DATE) is ClaimStatus.RULED_OUT:
        reasons.append(DELIVERY_DATE_RULED_OUT)
    return tuple(reasons)


def _needed_by_checks(option: OfferOption) -> tuple[ConstraintCheck, ...]:
    return tuple(check for check in option.constraint_checks if check.kind is ConstraintKind.NEEDED_BY)


def needed_by_result(option: OfferOption) -> CheckResult | None:
    """The least favourable result of the option's needed-by checks; `None` when it carries none."""
    results = [check.result for check in _needed_by_checks(option)]
    return max(results, key=_CHECK_RESULTS.index, default=None)


def needed_by_dates(option: OfferOption) -> tuple[str, ...]:
    """The date of each needed-by check that carries the least favourable result (`ConstraintCheck.subject`)."""
    worst = needed_by_result(option)
    return unique([check.subject for check in _needed_by_checks(option) if check.result is worst])
