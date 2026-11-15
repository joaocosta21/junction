"""Facts: every value a rule may read, taken from the offer option, the buyer profile and the order context.

Each fact declared in `rules.yaml` has exactly one reader here; the loader checks both directions.
A reader returns the value, or `Missing` with the reason. Missing is never turned into a default:
the condition that needed the fact stays unknown and rule F-03 sends the order to a human.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

from tta.contracts.allergen import AllergenFinding
from tta.contracts.availability import RevalidationChange, RevalidationResult
from tta.contracts.common import (
    AllergenOutcome,
    AllergenRelation,
    AllergenStrictness,
    ApproverRole,
    AvailabilityState,
    CheckResult,
    ClaimName,
    ClaimStatus,
    ConstraintKind,
    SubstitutionScope,
)
from tta.contracts.offer import OfferLine, OfferOption
from tta.contracts.policy import BuyerProfile, PolicyContext
from tta.policy.allergen_words import ALLERGEN_LINE_FACTS, ALLERGEN_PROFILE_FACTS, allergen_words
from tta.policy.claims import (
    CLAIM_WORDS,
    NEEDED_BY_NOT_ASKED,
    NEEDED_BY_WORDS,
    claim_status,
    needed_by_dates,
    needed_by_result,
    unconfirmed_reasons,
)
from tta.policy.coverage import (
    NOTHING_OFFERED,
    coverage_by_line,
    coverage_said,
    least_covered,
    line_names,
    lines_left_out,
)
from tta.policy.day_facts import DAY_FACTS
from tta.policy.formula_facts import FORMULA_FACTS
from tta.policy.human_approval import ROLE_NAMES, decided_as, dietitian_is_second_person
from tta.policy.last_resort_facts import LAST_RESORT_FACTS
from tta.policy.premium_facts import PREMIUM_ORDER_FACTS, PREMIUM_PROFILE_FACTS
from tta.policy.reading import Missing, Reading
from tta.policy.standing_facts import STANDING_FACTS
from tta.policy.text import format_datetime, join_words, plain_name, unique

ScopeTable = Mapping[SubstitutionScope, tuple[str, ...]]

# Rule F-07 for the option as a whole, as one clause.
DATE_FINDING = "the needed-by date {date} {found} for this option"
ARRIVES_ON = "{product} arrives on {day}"
TOO_LATE = "{product} cannot be delivered by then"
ARRIVES_BY = "what is offered arrives by {day}"
DATE_NOT_CONFIRMED = "the delivery date of what is offered is not confirmed"
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

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
    "tax_rate": "the tax rate",
    "delivery_date": "the delivery date",
    "sales_unit": "the sales unit",
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
        return Missing(f"{plain_name(profile.display_name)} excludes no allergen and sets no allergen rule")
    return profile.allergen_strictness.value


def _scopes_allowed(profile: BuyerProfile, table: ScopeTable) -> Reading:
    return tuple(table.get(profile.substitution_without_approval, ()))


def _drift_ratio(profile: BuyerProfile, _: ScopeTable) -> Reading:
    ratio = profile.standing_order_drift_ratio
    if ratio is None:
        return Missing(f"{plain_name(profile.display_name)} sets no drift tolerance for standing orders")
    return ratio


PROFILE_FACTS: Mapping[str, Callable[[BuyerProfile, ScopeTable], Reading]] = {
    "profile.profile_id": lambda profile, _: profile.profile_id,
    # A visitor types the name of its own kitchen: read as data, like a product name.
    "profile.display_name": lambda profile, _: plain_name(profile.display_name),
    "profile.auto_order_enabled": lambda profile, _: profile.auto_order_enabled,
    "profile.max_order_net_eur": lambda profile, _: profile.max_order_net_eur,
    "profile.max_daily_net_eur": lambda profile, _: profile.max_daily_net_eur,
    "profile.min_fill_ratio": lambda profile, _: profile.min_fill_ratio,
    "profile.excluded_allergens": lambda profile, _: tuple(profile.excluded_allergens),
    "profile.allergen_strictness": _allergen_strictness,
    "profile.strict_allergens": lambda profile, _: profile.codes_under(AllergenStrictness.STRICT),
    "profile.declared_only_allergens": lambda profile, _: profile.codes_under(AllergenStrictness.DECLARED_ONLY),
    "profile.substitution_without_approval": lambda profile, _: profile.substitution_without_approval.value,
    "profile.substitution_scopes_allowed": _scopes_allowed,
    "profile.variable_weight": lambda profile, _: profile.variable_weight.value,
    "profile.deposits": lambda profile, _: profile.deposits.value,
    "profile.standing_order_drift_ratio": _drift_ratio,
    "profile.formula_matters": lambda profile, _: profile.formula_matters,
    **PREMIUM_PROFILE_FACTS,  # rule P-09: what a preference may cost
    **ALLERGEN_PROFILE_FACTS,  # the excluded allergens in words, and whether somebody holds the dietitian's role
    # Who really decides at this buyer (`tta.policy.human_approval`, decision B54: one person confirms).
    "profile.dietitian_is_second_person": lambda profile, _: dietitian_is_second_person(profile),
    "profile.dietitian_said": lambda profile, _: ROLE_NAMES[decided_as(profile, ApproverRole.DIETITIAN)],
    "profile.finance_said": lambda profile, _: ROLE_NAMES[decided_as(profile, ApproverRole.FINANCE)],
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


def _day(iso: str) -> str:
    """`2026-11-16` -> "Monday 16 Nov", as the offer says a day; text that is no date is said as it is."""
    try:
        value = date.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{WEEKDAYS[value.weekday()]} {value.day} {MONTHS[value.month - 1]}"


def _late_lines(option: OfferOption) -> tuple[OfferLine, ...]:
    return tuple(
        line for line in option.lines if claim_status(line, ClaimName.DELIVERY_DATE) is ClaimStatus.RULED_OUT
    )


def _late_said(line: OfferLine) -> str:
    """One product that misses the date: when it arrives, where the offer says so."""
    named = f"{plain_name(line.name)} ({line.product_id})"
    arrives = line.availability.available_date
    if arrives is None:
        return TOO_LATE.format(product=named)
    return ARRIVES_ON.format(product=named, day=_day(arrives.isoformat()))


def _needed_by_finding(scope: OrderScope) -> Reading:
    """Rule F-07 for the option, as one clause. The offer's check is "not met" for two different things, and the
    clause says which: a product that arrives too late (named once here, so the rule does not also fire per
    line), or a request line the option offers nothing for (a missing line is not a late date)."""
    option = scope.option
    result = needed_by_result(option)
    words = NEEDED_BY_WORDS.get(result) if result is not None else None
    if words is None:
        return Missing("the needed-by date is met, or the request gave none")
    dates = needed_by_dates(option)
    plain = DATE_FINDING.format(date=join_words(dates), found=words)
    if result is not CheckResult.NOT_MET:
        return plain
    late = join_words([_late_said(line) for line in _late_lines(option)])
    not_met = f"{plain}: {late}" if late else plain
    names = line_names(option)
    left_out = join_words([names[index] for index in lines_left_out(option)])
    if not left_out:
        return not_met
    nothing = NOTHING_OFFERED.format(names=left_out)
    if late:
        return f"{nothing}, and {not_met}"
    statuses = {claim_status(line, ClaimName.DELIVERY_DATE) for line in option.lines}
    in_time = statuses <= {ClaimStatus.CONFIRMED}
    rest = ARRIVES_BY.format(day=_day(dates[0])) if in_time and dates else DATE_NOT_CONFIRMED
    return f"{nothing}; {rest}"


def _coverage_said(scope: OrderScope) -> Reading:
    return coverage_said(scope.option, scope.profile.min_fill_ratio, plain_name(scope.profile.display_name))


def _coverage_by_line(scope: OrderScope) -> Reading:
    words = coverage_by_line(scope.option)  # what each request line gets, the least covered first
    return words if words is not None else Missing("the option carries no coverage per request line")


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
    "option.coverage_said": _coverage_said,
    "option.valid_until": _valid_until,
    "option.expired": _expired,
    "option.needed_by_check": _needed_by_check,
    "option.needed_by": _needed_by,
    "option.needed_by_finding": _needed_by_finding,
    "option.total_is_ceiling": lambda scope: scope.option.totals.is_ceiling,
    "option.total_excludes_deposits": lambda scope: scope.option.totals.excludes_deposits,
    "context.at_order_time": lambda scope: scope.context.at_order_time,
    **DAY_FACTS,  # the day's spend, rule P-02
    "order.stale_reason": _stale_reason,
    "revalidation.ok": _revalidation_ok,
    "revalidation.expired": _revalidation_expired,
    "revalidation.changes": _revalidation_changes,
    **STANDING_FACTS,  # rule P-08: a renewal of a standing order (task STAND-1)
    **PREMIUM_ORDER_FACTS,  # rule P-09: what a preference costs above the cheapest confirmed option
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
    result = needed_by_result(scope.option)
    # A product that misses a date the option's check already calls not met is named once, by the option's entry.
    reasons = unconfirmed_reasons(line, dated=result is not None, late_said=result is CheckResult.NOT_MET)
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
        return f"the allergen check does not cover {allergen_words(skipped)}"
    strict = AllergenStrictness.STRICT
    weaker = [
        finding.excluded_code for finding in check.findings
        if scope.profile.strictness_for(finding.excluded_code) is strict
        and (finding.strictness or check.strictness) is not strict
    ]
    if weaker:
        return (
            f"the allergen check was not run under the strict rule {plain_name(scope.profile.display_name)} sets "
            f"for {allergen_words(weaker)}"
        )
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
ROLE_SEPARATOR = "; "  # between the roles of two dishes, as `tta.menus.needs` joins them
ROLE_NOT_IN_TABLE = "(the role the request gives for it is not in the recipe table, so it is not shown)"
STAND_IN_NOT_IN_TABLE = "in place of an ingredient the request names, which is not in the recipe table"


@lru_cache(maxsize=1)
def _known_product_types() -> frozenset[str]:
    """The keys of the catalog's product-type table and every product type of the recipe table (the second is
    checked against the first when it loads; both are read here so neither check is assumed)."""
    # Imported here: tta.catalog and tta.menus are not needed to load the policy package.
    from tta.catalog.product_types import PRODUCT_TYPES_FILE, load_product_types
    from tta.menus.recipes import shipped_recipes

    in_recipes = {
        choice.product_type
        for recipe in shipped_recipes().values() for ingredient in recipe.ingredients
        for choice in (ingredient, *ingredient.alternatives)
    }
    return frozenset(load_product_types(PRODUCT_TYPES_FILE)) | frozenset(in_recipes)


def _stand_in_field(line: OfferLine, name: str) -> str:
    value = getattr(line, name, None)
    return plain_name(value.replace("_", " ")) if isinstance(value, str) else ""


def _line_product_type(scope: OrderScope, line: OfferLine) -> str:
    """The product type the line's request line asked for, from the option's constraint checks."""
    for check in scope.option.constraint_checks:
        if check.kind is ConstraintKind.PRODUCT_TYPE and check.request_line_index == line.request_line_index:
            return plain_name(check.subject.replace("_", " "))
    return OTHER_PRODUCT_TYPE


def _recipe_role(line: OfferLine) -> str | None:
    """The role of the stand-in line when the recipe table holds it, else None (review A3, finding F4). The role
    arrives in the request, and rule F-09's sentence is read by the person who signs: a role an agent wrote
    itself would speak there in the gateway's voice. Each part between "; " must be the role of an ingredient of
    the recipe's product type, as the menu planner writes it (`tta.menus.needs`)."""
    role = getattr(line, STAND_IN_FIELDS[1], None)
    if not isinstance(role, str) or not role:
        return None
    from tta.menus.recipes import shipped_recipes  # here: tta.menus is not needed to load the policy package

    known = {
        ingredient.role for recipe in shipped_recipes().values() for ingredient in recipe.ingredients
        if ingredient.product_type == getattr(line, STAND_IN_FIELDS[0], None)
    }
    return role if all(part in known for part in role.split(ROLE_SEPARATOR)) else None


def _stands_in_for(scope: OrderScope, line: OfferLine) -> Reading:
    """Rule F-09 (task MENU-1): `yoghurt in place of the recipe's quark, whose role is ...`; empty when the line
    stands in for nothing. The role is shown only when the recipe table holds it for that product type.

    What the line stands in for arrives in the request and the sentence is read by the person who signs (review
    L1): it is shown only when it is a product-type key of the catalog's table or of the recipe table. Anything
    else is not repeated, and its role with it; the reading is still not empty, so rule F-09 still fires."""
    recipe_type = _stand_in_field(line, STAND_IN_FIELDS[0])
    if not recipe_type:
        return ""
    if getattr(line, STAND_IN_FIELDS[0], None) not in _known_product_types():
        return f"{_line_product_type(scope, line)} {STAND_IN_NOT_IN_TABLE}"
    stands_in = f"{_line_product_type(scope, line)} in place of the recipe's {recipe_type}"
    if not getattr(line, STAND_IN_FIELDS[1], None):
        return stands_in
    role = _recipe_role(line)
    return f"{stands_in}, whose role is {plain_name(role)}" if role else f"{stands_in} {ROLE_NOT_IN_TABLE}"


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
    **ALLERGEN_LINE_FACTS,  # allergens and dietary claims in words, for the sentences of F-02, F-05, F-08 and P-04
    **FORMULA_FACTS,  # rule F-11: a substitute's formula where the formula matters
    **LAST_RESORT_FACTS,  # rule F-12: a substitute that is a last resort
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
