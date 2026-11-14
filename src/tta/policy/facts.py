"""Facts: every value a rule may read, taken from the offer option, the buyer profile and the order context.

Each fact declared in `rules.yaml` has exactly one reader here; the loader checks both directions.
A reader returns the value, or `Missing` with the reason. Missing is never turned into a default:
the condition that needed the fact stays unknown and rule F-03 sends the order to a human.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from tta.contracts.allergen import AllergenFinding
from tta.contracts.availability import RevalidationChange, RevalidationResult
from tta.contracts.common import (
    AllergenOutcome,
    AllergenRelation,
    AllergenStrictness,
    AvailabilityState,
    ClaimName,
    ClaimStatus,
    ConstraintKind,
    SubstitutionScope,
    round_money,
)
from tta.contracts.offer import OfferLine, OfferOption
from tta.contracts.policy import BuyerProfile, PolicyContext
from tta.policy.claims import (
    CLAIM_WORDS,
    NEEDED_BY_NOT_ASKED,
    NEEDED_BY_WORDS,
    claim_status,
    needed_by_dates,
    needed_by_result,
    unconfirmed_reasons,
)
from tta.policy.coverage import coverage_by_line, least_covered
from tta.policy.reading import Missing, Reading
from tta.policy.standing_facts import STANDING_FACTS
from tta.policy.text import format_datetime, join_words, plain_name, unique

ScopeTable = Mapping[SubstitutionScope, tuple[str, ...]]

# How close a substitute is to the product it replaces (rules.yaml, substitution_scopes).
SUBSTITUTE_LISTED = SubstitutionScope.LISTED_BY_SUPPLIER.value
SUBSTITUTE_SAME_CATEGORY = SubstitutionScope.SAME_CATEGORY.value
SUBSTITUTE_OUTSIDE = "OUTSIDE"
SAME_CATEGORY_DISTANCE = 0  # SubstituteInfo.category_distance: 0 is the same 5-digit category

RELATION_WORDS: Mapping[AllergenRelation, str] = {
    AllergenRelation.CONTAINS: "contains",
    AllergenRelation.MAY_CONTAIN: "may contain",
    AllergenRelation.UNDECLARED: "undeclared",
    AllergenRelation.NOT_STATED: "no statement",
    AllergenRelation.FREE_FROM: "free from",
}
# The `field` values of a RevalidationChange (tta.contracts.availability), in words.
CHANGED_FIELD_WORDS: Mapping[str, str] = {
    "price": "the price",
    "price_validity": "the price validity",
    "availability_state": "the availability",
    "available_amount": "the available amount",
    "cutoff": "the order cut-off",
}


@dataclass(frozen=True)
class OrderScope:
    """What one evaluation is about: an option, the profile in force and the order context."""

    option: OfferOption
    profile: BuyerProfile
    context: PolicyContext
    substitution_scopes: ScopeTable


# --- the buyer profile -------------------------------------------------------------------------------------

def _allergen_strictness(profile: BuyerProfile, _: ScopeTable) -> Reading:
    if profile.allergen_strictness is None:
        return Missing("the profile excludes no allergen and sets no allergen rule")
    return profile.allergen_strictness.value


def _scopes_allowed(profile: BuyerProfile, table: ScopeTable) -> Reading:
    return tuple(table.get(profile.substitution_without_approval, ()))


def _drift_ratio(profile: BuyerProfile, _: ScopeTable) -> Reading:
    ratio = profile.standing_order_drift_ratio
    return Missing("the profile sets no drift tolerance for standing orders") if ratio is None else ratio


PROFILE_FACTS: Mapping[str, Callable[[BuyerProfile, ScopeTable], Reading]] = {
    "profile.profile_id": lambda profile, _: profile.profile_id,
    "profile.auto_order_enabled": lambda profile, _: profile.auto_order_enabled,
    "profile.max_order_net_eur": lambda profile, _: profile.max_order_net_eur,
    "profile.max_daily_net_eur": lambda profile, _: profile.max_daily_net_eur,
    "profile.min_fill_ratio": lambda profile, _: profile.min_fill_ratio,
    "profile.excluded_allergens": lambda profile, _: tuple(profile.excluded_allergens),
    "profile.allergen_strictness": _allergen_strictness,
    "profile.substitution_without_approval": lambda profile, _: profile.substitution_without_approval.value,
    "profile.substitution_scopes_allowed": _scopes_allowed,
    "profile.variable_weight": lambda profile, _: profile.variable_weight.value,
    "profile.deposits": lambda profile, _: profile.deposits.value,
    "profile.standing_order_drift_ratio": _drift_ratio,
}


# --- the option and the order context ----------------------------------------------------------------------

def _valid_until(scope: OrderScope) -> Reading:
    valid_until = scope.option.valid_until
    return valid_until if valid_until is not None else Missing("the option carries no valid-until time")


def _expired(scope: OrderScope) -> Reading:
    """Expired from the moment of its valid-until, as a cut-off equal to the clock has passed (SPEC section 4)."""
    valid_until = scope.option.valid_until
    if valid_until is None:
        return Missing("the option carries no valid-until time")
    now = scope.context.now
    if (valid_until.tzinfo is None) != (now.tzinfo is None):
        return Missing("the option's valid-until time and the clock cannot be compared: one has no offset")
    return valid_until <= now


def _needed_by_check(scope: OrderScope) -> Reading:
    """The result of the needed-by check as the offer gives it. No check: the request gave no date."""
    result = needed_by_result(scope.option)
    return NEEDED_BY_NOT_ASKED if result is None else result.value


def _needed_by(scope: OrderScope) -> Reading:
    dates = needed_by_dates(scope.option)
    return join_words(dates) if dates else Missing("the request gave no needed-by date")


def _needed_by_finding(scope: OrderScope) -> Reading:
    """In words, what the needed-by check found when it is not met."""
    result = needed_by_result(scope.option)
    words = NEEDED_BY_WORDS.get(result) if result is not None else None
    return words if words is not None else Missing("the needed-by date is met, or the request gave none")


def _coverage_by_line(scope: OrderScope) -> Reading:
    words = coverage_by_line(scope.option)  # what each request line gets, the least covered first
    return words if words is not None else Missing("the option carries no coverage per request line")


def _day_committed(scope: OrderScope) -> Reading:
    committed = scope.context.day_committed_net_eur
    if committed is None:
        return Missing("today's committed spend did not come with the order context")
    return round_money(committed)


def _day_net(scope: OrderScope) -> Reading:
    committed = scope.context.day_committed_net_eur
    if committed is None:
        return Missing("today's committed spend did not come with the order context")
    return round_money(committed + scope.option.totals.net)


def _revalidation(scope: OrderScope) -> RevalidationResult | Missing:
    result = scope.context.revalidation
    return result if result is not None else Missing("no fresh price and availability check came with the order")


def _revalidation_ok(scope: OrderScope) -> Reading:
    """True only when the fresh check says ok and reports neither an expiry nor a change."""
    result = _revalidation(scope)
    if isinstance(result, Missing):
        return result
    return result.ok and not result.expired and not result.changes


def _revalidation_expired(scope: OrderScope) -> Reading:
    result = _revalidation(scope)
    return result if isinstance(result, Missing) else result.expired


def _change_clause(change: RevalidationChange) -> str:
    what = CHANGED_FIELD_WORDS.get(change.field, f"the {change.field.replace('_', ' ')}")
    return f"{what} of {change.product_id} changed from {change.before} to {change.after}"


def _revalidation_changes(scope: OrderScope) -> Reading:
    result = _revalidation(scope)
    return result if isinstance(result, Missing) else tuple(_change_clause(change) for change in result.changes)


def _stale_reason(scope: OrderScope) -> Reading:
    """Why the option can no longer be ordered as offered, as one clause."""
    parts: list[str] = []
    option_expired = _expired(scope) is True
    if option_expired and scope.option.valid_until is not None:
        parts.append(f"it was valid until {format_datetime(scope.option.valid_until)}")
    result = scope.context.revalidation
    if result is not None:
        if result.expired and not option_expired:
            parts.append("a price validity or an order cut-off has passed")
        parts.extend(_change_clause(change) for change in result.changes)
        if not parts and not result.ok:
            parts.append("the fresh check of price and availability did not confirm it")
    return join_words(parts) if parts else Missing("nothing says why")


ORDER_FACTS: Mapping[str, Callable[[OrderScope], Reading]] = {
    "option.net_eur": lambda scope: scope.option.totals.net,
    "option.fill_ratio": lambda scope: scope.option.fill_ratio,
    "option.least_covered": lambda scope: least_covered(scope.option),
    "option.coverage_by_line": _coverage_by_line,
    "option.valid_until": _valid_until,
    "option.expired": _expired,
    "option.needed_by_check": _needed_by_check,
    "option.needed_by": _needed_by,
    "option.needed_by_finding": _needed_by_finding,
    "option.total_is_ceiling": lambda scope: scope.option.totals.is_ceiling,
    "option.total_excludes_deposits": lambda scope: scope.option.totals.excludes_deposits,
    "context.at_order_time": lambda scope: scope.context.at_order_time,
    "context.day_committed_net_eur": _day_committed,
    "order.day_net_eur": _day_net,
    "order.stale_reason": _stale_reason,
    "revalidation.ok": _revalidation_ok,
    "revalidation.expired": _revalidation_expired,
    "revalidation.changes": _revalidation_changes,
    **STANDING_FACTS,  # rule P-08: a renewal of a standing order (task STAND-1)
}


# --- one line of the option --------------------------------------------------------------------------------

def _no_claim(claim: ClaimName) -> Missing:
    """A claim the line does not carry is a missing fact (SPEC section 4): it is never read as confirmed."""
    return Missing(f"the offer line carries no {CLAIM_WORDS[claim]} claim")


def _quantity_confirmed(_: OrderScope, line: OfferLine) -> Reading:
    """State CONFIRMED and a quantity claim that says CONFIRMED (SPEC section 4)."""
    if line.availability.state is not AvailabilityState.CONFIRMED:
        return False  # the state settles it, with or without a claim
    status = claim_status(line, ClaimName.QUANTITY)
    return _no_claim(ClaimName.QUANTITY) if status is None else status is ClaimStatus.CONFIRMED


def _claim(claim: ClaimName) -> Callable[[OrderScope, OfferLine], Reading]:
    """A reader for the verification status of one claim of a line, as the offer carries it."""

    def read(_: OrderScope, line: OfferLine) -> Reading:
        status = claim_status(line, claim)
        return _no_claim(claim) if status is None else status.value

    return read


def _unconfirmed_reason(scope: OrderScope, line: OfferLine) -> Reading:
    """Why the line cannot be ordered without a human under rule F-07, as one clause."""
    reasons = unconfirmed_reasons(line, dated=needed_by_result(scope.option) is not None)
    return join_words(reasons) if reasons else Missing("nothing says why")


def _allergen_gap(scope: OrderScope, line: OfferLine) -> str | None:
    """Why the line's allergen check cannot be relied on for this profile; None when it can."""
    excluded = scope.profile.excluded_allergens
    check = line.allergen_check
    if check is None:
        # OfferLine.allergen_check is None when the buyer excluded nothing (tta.contracts.offer).
        return "no allergen check came with this line" if excluded else None
    covered = {finding.excluded_code for finding in check.findings}
    skipped = [code for code in excluded if code not in covered]
    if skipped:
        return f"the allergen check does not cover {', '.join(skipped)}"
    profile_is_strict = scope.profile.allergen_strictness is AllergenStrictness.STRICT
    if profile_is_strict and check.strictness is not AllergenStrictness.STRICT:
        return "the allergen check was not run under the profile's STRICT rule"
    return None


def _allergen_outcomes(scope: OrderScope, line: OfferLine) -> Reading:
    """Every outcome the allergen check reports: its own and that of each finding.

    The outcome is read, never the relation: the table of SPEC section 6 belongs to the allergen
    package. Oats declared under a "no gluten" exclusion, for one, go to a human and are not rejected.
    """
    check = line.allergen_check
    known: tuple[str, ...] = ()
    if check is not None:
        known = unique([check.outcome.value, *(finding.outcome.value for finding in check.findings)])
    gap = _allergen_gap(scope, line)
    return known if gap is None else Missing(gap, known=known)


def _describe_finding(finding: AllergenFinding) -> str:
    words = RELATION_WORDS[finding.relation]
    about_member = finding.matched_code is not None and finding.matched_code != finding.excluded_code
    stated_for = f", stated for {finding.matched_code}" if about_member else ""
    return f"{finding.excluded_code} ({words}{stated_for})"


def _findings(line: OfferLine, outcome: AllergenOutcome) -> tuple[str, ...]:
    if line.allergen_check is None:
        return ()
    return tuple(
        _describe_finding(finding) for finding in line.allergen_check.findings if finding.outcome is outcome
    )


def _substitute_original(_: OrderScope, line: OfferLine) -> Reading:
    substitute = line.substitute
    if substitute is None:
        return Missing("the line replaces no product")
    if substitute.original_name:
        return f"{plain_name(substitute.original_name)} ({substitute.original_id})"
    return substitute.original_id


def _substitute_scope(_: OrderScope, line: OfferLine) -> Reading:
    substitute = line.substitute
    if substitute is None:
        return Missing("the line replaces no product")
    if substitute.listed_by_supplier:
        return SUBSTITUTE_LISTED
    return SUBSTITUTE_SAME_CATEGORY if substitute.category_distance == SAME_CATEGORY_DISTANCE else SUBSTITUTE_OUTSIDE


def _substitute_adds_allergen(_: OrderScope, line: OfferLine) -> Reading:
    """The verdict of the substitution rule (SPEC section 6), as the allergen package gave it."""
    return line.substitute is not None and not line.substitute.allergen_check.passes


def _substitute_added_allergens(_: OrderScope, line: OfferLine) -> Reading:
    if line.substitute is None:
        return ()
    added = line.substitute.allergen_check.added
    return tuple(f"{statement.code} ({RELATION_WORDS[statement.relation]})" for statement in added)


def _substitute_claims_lost(_: OrderScope, line: OfferLine) -> Reading:
    """The nutritional claims of the original that the substitute does not carry, as the offer lists them.

    They are codes from the product file (FREE_FROM_LACTOSE), so they are neutralised like a name.
    """
    if line.substitute is None:
        return ()
    return tuple(plain_name(claim) for claim in line.substitute.claims_lost)


def _variable_weight(_: OrderScope, line: OfferLine) -> Reading:
    # variableUnit is absent on 3,068 of the 17,546 catalog products (AIMO/FINDINGS.md section 4).
    if line.variable_weight is None:
        return Missing("the product file does not say whether it is sold by variable weight")
    return line.variable_weight


# Copied from the request line onto the offer line (task MENU-1): the recipe's product type and its role.
STAND_IN_FIELDS = ("stands_in_for", "stands_in_role")
OTHER_PRODUCT_TYPE = "another product type"


def _stand_in_field(line: OfferLine, name: str) -> str:
    value = getattr(line, name, None)
    return plain_name(value.replace("_", " ")) if isinstance(value, str) else ""


def _line_product_type(scope: OrderScope, line: OfferLine) -> str:
    """The product type the line's request line asked for, from the option's constraint checks."""
    for check in scope.option.constraint_checks:
        if check.kind is ConstraintKind.PRODUCT_TYPE and check.request_line_index == line.request_line_index:
            return plain_name(check.subject.replace("_", " "))
    return OTHER_PRODUCT_TYPE


def _stands_in_for(scope: OrderScope, line: OfferLine) -> Reading:
    """Rule F-09 (task MENU-1): `yoghurt in place of the recipe's quark, whose role is ...`; empty when the line
    stands in for nothing. Product types and the role are text of the request, so they are read as data."""
    recipe_type, role = (_stand_in_field(line, name) for name in STAND_IN_FIELDS)
    if not recipe_type:
        return ""
    stands_in = f"{_line_product_type(scope, line)} in place of the recipe's {recipe_type}"
    return f"{stands_in}, whose role is {role}" if role else stands_in


LINE_FACTS: Mapping[str, Callable[[OrderScope, OfferLine], Reading]] = {
    "line.product_id": lambda _, line: line.product_id,
    "line.name": lambda _, line: plain_name(line.name),
    "line.quantity": lambda _, line: line.quantity,
    "line.availability_state": lambda _, line: line.availability.state.value,
    "line.quantity_confirmed": _quantity_confirmed,
    "line.price_claim": _claim(ClaimName.PRICE),
    "line.delivery_date_claim": _claim(ClaimName.DELIVERY_DATE),
    "line.unconfirmed_reason": _unconfirmed_reason,
    "line.allergen_outcomes": _allergen_outcomes,
    "line.allergens_declared": lambda _, line: _findings(line, AllergenOutcome.REJECT),
    "line.allergens_to_human": lambda _, line: _findings(line, AllergenOutcome.TO_HUMAN),
    "line.is_substitute": lambda _, line: line.substitute is not None,
    "line.substitute_original": _substitute_original,
    "line.substitute_scope": _substitute_scope,
    "line.substitute_adds_allergen": _substitute_adds_allergen,
    "line.substitute_added_allergens": _substitute_added_allergens,
    "line.substitute_claims_lost": _substitute_claims_lost,
    "line.variable_weight": _variable_weight,
    "line.has_deposits": lambda _, line: line.has_deposits,
    "line.stands_in_for": _stands_in_for,
}

LINE_FACT_PREFIX = "line."
PROFILE_FACT_PREFIX = "profile."
KNOWN_FACTS: frozenset[str] = frozenset(PROFILE_FACTS) | frozenset(ORDER_FACTS) | frozenset(LINE_FACTS)


def read_profile_fact(name: str, profile: BuyerProfile, substitution_scopes: ScopeTable) -> Reading:
    """A `profile.*` fact. Any other name is missing here: the profile alone cannot answer it."""
    reader = PROFILE_FACTS.get(name)
    return reader(profile, substitution_scopes) if reader else Missing("not a setting of the buyer profile")


def read_fact(name: str, scope: OrderScope, line: OfferLine | None = None) -> Reading:
    """Any declared fact. A line fact asked for without a line is missing, never guessed."""
    if name in PROFILE_FACTS:
        return PROFILE_FACTS[name](scope.profile, scope.substitution_scopes)
    if name in ORDER_FACTS:
        return ORDER_FACTS[name](scope)
    if name in LINE_FACTS:
        return LINE_FACTS[name](scope, line) if line is not None else Missing("it is a fact about one line")
    return Missing("the engine has no reader for it")
