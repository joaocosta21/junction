"""What the rules decide, as a table: with ordering alone ON, what the agent orders and what is stopped.

Every shipped customer leaves ordering alone off, so every order goes to a person anyway and the rules only
change the reason shown. This file switches it ON for a copy of each shipped profile (nothing else differs)
and walks hand-built options through the engine. `CASES` is the documentation of what the rules decide: one row
per case, and for each customer one of

    ALONE                            the agent places the order, nobody is asked
    PERSON <rules> -> <roles>        the order waits for the people named; the rules are the reasons
    NEVER <rules>                    the order cannot be placed, even with approval

`SENTENCES` is what the person reads, in full, for at least one case of every rule.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest

from tta.contracts.common import (
    AllergenRelation,
    AvailabilityState,
    CheckResult,
    ClaimStatus,
    ConstraintKind,
    Unit,
    Verdict,
)
from tta.contracts.offer import ConstraintCheck, Coverage, OfferLine, OfferOption, SubstituteInfo
from tta.contracts.policy import BuyerProfile, PolicyContext, PolicyDecision
from tta.contracts.product import FormulaCheck, FormulaOutcome, NutrientDifference, ReplaceCheck, ReplaceVerdict
from tta.contracts.standing import Renewal, RenewalLine, StandingHistory
from tta.policy import PROFILES_DIR, RULES_PATH, RulePolicyEngine, load_profiles, load_rulebook

HOTEL, SCHOOL, WARD, BAKERY = "hotel-kitchen", "school-kitchen", "allergy-ward", "bakery-cafe"
CUSTOMERS = (HOTEL, SCHOOL, WARD, BAKERY)
ALONE = "ALONE"
MILK = "Arla Café milk 1 L UHT (463380)"
KEPT = FormulaCheck(outcome=FormulaOutcome.OTHER_BRAND, sentence="Same formula within our tolerance.")
DIFFERENT = FormulaCheck(
    outcome=FormulaOutcome.DIFFERENT,
    differences=(NutrientDifference(nutrient="fat", original=Decimal(36), other=Decimal(15), within_tolerance=False),),
    sentence="Different formula: fat 15 g, not 36 g per 100 g.",
)
FLAVOURED = "flavoured with nut and vanilla; the product asked for is not flavoured"
OTHER_FORMULA = "a different formula (fat 15 g, not 36 g)"  # as the offer words the reason for `DIFFERENT`
LIKE_FOR_LIKE = ReplaceCheck(
    verdict=ReplaceVerdict.REPLACEABLE,
    sentence="Replaceable: same type, same use, no flavour named, same formula within tolerance.",
)


class _Line(OfferLine):
    """An offer line with the fields a request line hands down (`stands_in_for`, `keep_formula`)."""

    stands_in_for: str | None = None
    stands_in_role: str | None = None
    keep_formula: bool | None = None


@dataclass(frozen=True)
class Kit:
    """The builders of `conftest.py` for one customer. A line built here states every allergen the customer
    excludes as free-from unless the case says otherwise, so that a case shows one thing at a time."""

    profile: BuyerProfile
    make_line: Callable[..., OfferLine]
    make_option: Callable[..., OfferOption]
    make_context: Callable[..., PolicyContext]
    make_substitute: Callable[..., SubstituteInfo]
    make_allergen_check: Callable[..., Any]
    make_revalidation: Callable[..., Any]
    now: Any

    def line(self, *args: Any, states: dict[str, AllergenRelation] | None = None, **fields: Any) -> OfferLine:
        """`states`: what the product says about an allergen, when the customer excludes it."""
        excluded = self.profile.excluded_allergens
        relations = {code: (states or {}).get(code, AllergenRelation.FREE_FROM) for code in excluded}
        handed_down = ("stands_in_for", "stands_in_role", "keep_formula")
        extra = {name: fields.pop(name) for name in handed_down if name in fields}
        check = self.make_allergen_check(relations) if excluded else None
        plain = self.make_line(*args, allergen_check=check, **fields)
        return _Line.model_validate({**dict(plain), **extra}) if extra else plain

    def stand_in(
        self, *, last_resort: str | None = None, formula: FormulaCheck = KEPT, **substitute: Any
    ) -> SubstituteInfo:
        """A substitute for the oat drink 473609: listed by Valio Aimo and like for like unless the case says not.
        It carries the offer's like-for-like verdict as the offer builds it (`tta.offers.substitutes`): not like
        for like as soon as there is a reason against it (a flavour, a lost dietary claim, another formula)."""
        lost = tuple(substitute.get("claims_lost", ()))
        reasons = (
            *((last_resort,) if last_resort is not None else ()),
            *(f"it does not carry the claim {claim}" for claim in lost),
            *((OTHER_FORMULA,) if formula is DIFFERENT else ()),
        )
        replaceable = ReplaceCheck(
            verdict=ReplaceVerdict.NOT_LIKE_FOR_LIKE, reasons=reasons,
            sentence=f"Not a like-for-like replacement: {'; '.join(reasons)}.",
        ) if reasons else LIKE_FOR_LIKE
        return self.make_substitute(**substitute).model_copy(
            update={"formula": formula, "last_resort": last_resort is not None, "replaceable": replaceable}
        )

    def judge(self, lines: list[OfferLine] | None = None, *, context: PolicyContext | None = None, **option: Any):
        return self.make_option(lines or [self.line()], **option), context or self.make_context()


Built = tuple[OfferOption, PolicyContext]


# --- the cases: each builds one option (and its order context) for one customer -------------------------------

def everything_confirmed(kit: Kit) -> Built:
    return kit.judge()


def quantity_not_confirmed(kit: Kit) -> Built:
    return kit.judge([kit.line(state=AvailabilityState.QUANTITY_NOT_CONFIRMED)])


def price_not_confirmed(kit: Kit) -> Built:
    return kit.judge([kit.line(price_claim=ClaimStatus.UNKNOWN)])


def needed_by_not_verified(kit: Kit) -> Built:
    return kit.judge(needed_by=CheckResult.UNVERIFIED)


def variable_weight_not_stated(kit: Kit) -> Built:
    return kit.judge([kit.line(variable_weight=None)])


def origin_not_confirmed(kit: Kit) -> Built:
    return kit.judge([kit.line(origin_claim=ClaimStatus.UNKNOWN)])


def contains_peanuts(kit: Kit) -> Built:
    return kit.judge([kit.line("400001", "Peanut butter biscuit", states={"AP": AllergenRelation.CONTAINS})])


def contains_milk(kit: Kit) -> Built:
    return kit.judge([kit.line(states={"AM": AllergenRelation.CONTAINS})])


def may_contain_tree_nuts(kit: Kit) -> Built:
    return kit.judge([kit.line("400002", "Oat biscuit", states={"AN": AllergenRelation.MAY_CONTAIN})])


def says_nothing_about_sesame(kit: Kit) -> Built:
    return kit.judge([kit.line("400002", "Oat biscuit", states={"AS": AllergenRelation.NOT_STATED})])


def substitute_adds_gluten(kit: Kit) -> Built:
    """Oatly iKaffe for a product that declares no gluten cereal: the allergen rule for substitutes fails."""
    adds = kit.stand_in(added=(("GO", AllergenRelation.CONTAINS), ("AW", AllergenRelation.CONTAINS)))
    return kit.judge([kit.line("464320", "Oatly iKaffe", states={"AW": AllergenRelation.CONTAINS}, substitute=adds)])


def substitute_adds_tree_nuts(kit: Kit) -> Built:
    adds = kit.stand_in(added=(("AN", AllergenRelation.CONTAINS),))
    return kit.judge([kit.line("474724", "Nutty oat drink", states={"AN": AllergenRelation.CONTAINS}, substitute=adds)])


def the_same_product_asked_for_by_name(kit: Kit) -> Built:
    """Oatly iKaffe as the product the buyer named: no substitute, so only the allergen rules of any product."""
    return kit.judge([kit.line("464320", "Oatly iKaffe", states={"AW": AllergenRelation.CONTAINS})])


def listed_like_for_like_substitute(kit: Kit) -> Built:
    return kit.judge([kit.line("471690", "Oat drink", substitute=kit.stand_in())])


def unlisted_same_category_substitute(kit: Kit) -> Built:
    return kit.judge([kit.line("471690", "Oat drink", substitute=kit.stand_in(listed=False))])


def substitute_not_lactose_free(kit: Kit) -> Built:
    lost = kit.stand_in(claims_lost=("FREE_FROM_LACTOSE",))
    return kit.judge([kit.line("463149", "Valio Plus skimmed milk 1 l", substitute=lost)])


def flavoured_last_resort(kit: Kit) -> Built:
    return kit.judge([kit.line("474724", "Nutty vanilla oat drink", substitute=kit.stand_in(last_resort=FLAVOURED))])


def other_formula_where_the_request_says_it_matters(kit: Kit) -> Built:
    other = kit.stand_in(formula=DIFFERENT)
    return kit.judge([kit.line("471690", "Cooking cream 15%", substitute=other, keep_formula=True)])


def other_formula_where_nobody_says_it_matters(kit: Kit) -> Built:
    return kit.judge([kit.line("471690", "Cooking cream 15%", substitute=kit.stand_in(formula=DIFFERENT))])


def recipe_stand_in(kit: Kit) -> Built:
    option, context = kit.judge([kit.line("464615", "Greek natural yoghurt 1 kg", stands_in_for="quark")])
    asked = ConstraintCheck(
        request_line_index=0, kind=ConstraintKind.PRODUCT_TYPE, subject="yoghurt", result=CheckResult.MET,
        sentence="The product is of type yoghurt.",
    )
    return option.model_copy(update={"constraint_checks": (*option.constraint_checks, asked)}), context


def expired_when_the_order_is_placed(kit: Kit) -> Built:
    context = kit.make_context(at_order_time=True, revalidation=kit.make_revalidation())
    return kit.judge(valid_until=kit.now - timedelta(minutes=1), context=context)


def price_changed_since_the_offer(kit: Kit) -> Built:
    changed = kit.make_revalidation(ok=False, changed_price=True)
    return kit.judge(context=kit.make_context(at_order_time=True, revalidation=changed))


def one_euro_above_the_limit_per_order(kit: Kit) -> Built:
    return kit.judge(net=str(kit.profile.max_order_net_eur + 1))


def the_day_already_at_its_limit(kit: Kit) -> Built:
    return kit.judge(context=kit.make_context(str(kit.profile.max_daily_net_eur)))


def half_the_quantity_covered(kit: Kit) -> Built:
    return kit.judge(fill_ratio="0.5")


def sold_by_variable_weight(kit: Kit) -> Built:
    return kit.judge([kit.line("400003", "Beef sirloin", variable_weight=True)], is_ceiling=True)


def carries_a_deposit(kit: Kit) -> Built:
    return kit.judge([kit.line("400004", "Mineral water 0.5 l", has_deposits=True)], excludes_deposits=True)


def renewal_at_twice_the_usual_quantity(kit: Kit) -> Built:
    """A standing order of 100 units a week, six weeks on record, renewed at 200."""
    past = tuple(
        Renewal(
            renewal_id=f"ren_{week}", standing_order_id="so_milk", renewed_at=kit.now - timedelta(weeks=7 - week),
            lines=(RenewalLine(request_line_index=0, product_id="463380", quantity=Decimal(100), unit=Unit.L,
                               unit_net_price_eur=Decimal("1.00")),),
            synthetic=True,
        )
        for week in range(6)
    )
    history = StandingHistory(standing_order_id="so_milk", name="Weekly milk", renewals=past)
    line = kit.line(quantity="200", unit_net_price="1.00")
    option = kit.make_option([line], net="200.00", needed_by=None)
    coverage = Coverage(request_line_index=0, requested=Decimal(200), covered=Decimal(200), unit=Unit.L,
                        fill_ratio=Decimal(1), missing=Decimal(0))
    context = PolicyContext(now=kit.now, day_committed_net_eur=Decimal(0), standing_history=history)
    return option.model_copy(update={"coverage": (coverage,)}), context


def preferred_option_a_fifth_dearer(kit: Kit) -> Built:
    option, context = kit.judge(net="120.00")
    return option.model_copy(update={"net_above_cheapest": Decimal("20.00")}), context


def all_of(outcome: str, **other: str) -> dict[str, str]:
    """The same outcome for every customer, except the ones named: `school="..."`."""
    names = {"hotel": HOTEL, "school": SCHOOL, "ward": WARD, "bakery": BAKERY}
    return {**dict.fromkeys(CUSTOMERS, outcome), **{names[name]: said for name, said in other.items()}}


PM, DIET, FIN = "purchasing_manager", "dietitian", "finance"
# The ward and the bakery take no substitute alone (P-05), so every substitute also asks their purchasing manager.
CASES: list[tuple[Callable[[Kit], Built], dict[str, str]]] = [
    # --- nothing stands in the way
    (everything_confirmed, all_of(ALONE)),
    # --- anything Valio Aimo's data does not confirm goes to a person
    (quantity_not_confirmed, all_of(f"PERSON F-01 -> {PM}")),
    (price_not_confirmed, all_of(f"PERSON F-07 -> {PM}")),
    (needed_by_not_verified, all_of(f"PERSON F-07 -> {PM}")),
    (variable_weight_not_stated, all_of(f"PERSON F-03 -> {PM}")),
    (origin_not_confirmed, all_of(f"PERSON F-10 -> {PM}")),
    # --- an allergen you exclude is never ordered; one the data does not rule out goes to the dietitian
    (contains_peanuts, all_of(ALONE, school="NEVER F-02")),
    (contains_milk, all_of(ALONE, ward="NEVER F-02")),
    (may_contain_tree_nuts, all_of(ALONE, school=f"PERSON P-04 -> {DIET}")),
    (says_nothing_about_sesame, all_of(ALONE, school=f"PERSON P-04 -> {DIET}")),
    # --- a substitute that adds an allergen is never ordered, for any customer; asked for by name it is a product
    (substitute_adds_gluten, all_of("NEVER F-05", ward="NEVER F-02, F-05")),
    (substitute_adds_tree_nuts, all_of("NEVER F-05", school="NEVER F-02, F-05")),
    (the_same_product_asked_for_by_name, all_of(ALONE, ward="NEVER F-02")),
    # --- a substitute that is not a like-for-like replacement goes to a person
    (listed_like_for_like_substitute, all_of(ALONE, ward=f"PERSON P-05 -> {PM}", bakery=f"PERSON P-05 -> {PM}")),
    (unlisted_same_category_substitute, all_of(f"PERSON P-05 -> {PM}", hotel=ALONE)),
    (substitute_not_lactose_free, all_of(f"PERSON F-08 -> {DIET}", ward=f"PERSON F-08, P-05 -> {PM}, {DIET}",
                                         bakery=f"PERSON F-08, P-05 -> {PM}, {DIET}")),
    # A formula, a flavour or a use that differs is the dietitian's question where the customer has a dietitian of
    # its own (the school, the ward); at the hotel and the bakery the person who orders decides it (decision B66).
    (flavoured_last_resort, all_of(f"PERSON F-12 -> {PM}", school=f"PERSON F-12 -> {DIET}",
                                   ward=f"PERSON F-12, P-05 -> {PM}, {DIET}", bakery=f"PERSON F-12, P-05 -> {PM}")),
    (other_formula_where_the_request_says_it_matters, all_of(
        f"PERSON F-11 -> {PM}", school=f"PERSON F-11 -> {DIET}", ward=f"PERSON F-11, P-05 -> {PM}, {DIET}",
        bakery=f"PERSON F-11, P-05 -> {PM}")),
    # Nobody says the formula matters: the substitute is still not like for like, and no customer's agent takes
    # it alone (until 15 Nov 2026 the hotel's did: check CK3). The bakery says the formula matters on every line,
    # so there the formula rule says the difference, once.
    (other_formula_where_nobody_says_it_matters, all_of(
        f"PERSON F-12 -> {PM}", school=f"PERSON F-12 -> {DIET}", ward=f"PERSON F-12, P-05 -> {PM}, {DIET}",
        bakery=f"PERSON F-11, P-05 -> {PM}")),
    (recipe_stand_in, all_of(f"PERSON F-09 -> {PM}")),
    # --- an offer that is out of date cannot be ordered
    (expired_when_the_order_is_placed, all_of("NEVER F-04")),
    (price_changed_since_the_offer, all_of("NEVER F-04")),
    # --- each customer's own limits
    (one_euro_above_the_limit_per_order, all_of(f"PERSON P-01 -> {PM}")),
    (the_day_already_at_its_limit, all_of(f"PERSON P-02 -> {FIN}")),
    (half_the_quantity_covered, all_of(f"PERSON P-03 -> {PM}")),
    (sold_by_variable_weight, all_of(f"PERSON P-06 -> {PM}")),
    (carries_a_deposit, all_of(f"PERSON P-07 -> {FIN}")),
    (renewal_at_twice_the_usual_quantity, all_of(f"PERSON P-08 -> {PM}")),
    # The hotel and the school set no limit on what a preference may cost; the ward and the bakery set 10%.
    (preferred_option_a_fifth_dearer, all_of(ALONE, ward=f"PERSON P-09 -> {PM}", bakery=f"PERSON P-09 -> {PM}")),
]

# What the person reads: (rule, case, customer, the rule's whole sentence).
SENTENCES: list[tuple[str, Callable[[Kit], Built], str, str]] = [
    ("F-01", quantity_not_confirmed, HOTEL, f"The quantity of 100 × {MILK} is not confirmed by Valio Aimo."),
    ("F-02", contains_peanuts, SCHOOL,
     "Peanut butter biscuit (400001) contains peanuts, which is excluded for Kilo School, so it cannot be ordered."),
    ("F-02", the_same_product_asked_for_by_name, WARD,
     "Oatly iKaffe (464320) contains cereals containing gluten, which is excluded for City Hospital, Ward 4, so it "
     "cannot be ordered."),
    ("F-03", variable_weight_not_stated, HOTEL,
     f"The variable-weight statement of {MILK} is missing (the product file does not say whether it is sold by "
     "variable weight), so rule P-06 cannot be checked."),
    ("F-04", expired_when_the_order_is_placed, HOTEL,
     "This option can no longer be ordered as offered: it was valid until 2026-11-14 02:51+02:00."),
    ("F-04", price_changed_since_the_offer, HOTEL,
     "This option can no longer be ordered as offered: the price of 463380 changed from 2.65 to 2.80."),
    ("F-05", substitute_adds_gluten, HOTEL,
     "Oatly iKaffe (464320) would replace Oddlygood Barista oat drink (473609) and declares that it contains oats "
     "and cereals containing gluten, which the product asked for does not, so it cannot be ordered as a substitute. "
     "Ask for it by name if you want it."),
    ("F-07", price_not_confirmed, HOTEL, f"For {MILK} the price is not confirmed by Valio Aimo."),
    ("F-07", needed_by_not_verified, HOTEL,
     "The needed-by date 2026-11-16 cannot be verified for this option."),
    ("F-08", substitute_not_lactose_free, SCHOOL,
     "Valio Plus skimmed milk 1 l (463149) would replace Oddlygood Barista oat drink (473609) but is not marked "
     "lactose-free, as the product asked for is."),
    ("F-09", recipe_stand_in, HOTEL,
     "Greek natural yoghurt 1 kg (464615) stands in for an ingredient of a recipe: yoghurt in place of the recipe's "
     "quark, so a person checks that the dish still works."),
    ("F-10", origin_not_confirmed, HOTEL,
     "Not every statement of the offer is confirmed, so a person confirms the order."),
    ("F-11", other_formula_where_the_request_says_it_matters, HOTEL,
     "Cooking cream 15% (471690) would replace Oddlygood Barista oat drink (473609) where the formula matters (the "
     "request says so for this line), and the data does not show the same formula: Different formula: fat 15 g, not "
     "36 g per 100 g."),
    ("F-11", other_formula_where_nobody_says_it_matters, BAKERY,
     "Cooking cream 15% (471690) would replace Oddlygood Barista oat drink (473609) where the formula matters "
     "(Kallio Bakery uses its products as ingredients), and the data does not show the same formula: Different "
     "formula: fat 15 g, not 36 g per 100 g."),
    ("F-12", flavoured_last_resort, HOTEL,
     "Nutty vanilla oat drink (474724) would replace Oddlygood Barista oat drink (473609) and is not a "
     "like-for-like replacement: flavoured with nut and vanilla; the product asked for is not flavoured. A person "
     "decides whether it will do."),
    ("F-12", other_formula_where_nobody_says_it_matters, HOTEL,
     "Cooking cream 15% (471690) would replace Oddlygood Barista oat drink (473609) and is not a like-for-like "
     "replacement: a different formula (fat 15 g, not 36 g). A person decides whether it will do."),
    ("P-01", one_euro_above_the_limit_per_order, SCHOOL,
     "The total of €251.00 before tax is above the €250 limit per order of Kilo School."),
    ("P-02", the_day_already_at_its_limit, SCHOOL,
     "With this order today's spend would reach €900.00 before tax, above the €800 limit per day of Kilo School."),
    ("P-03", half_the_quantity_covered, HOTEL,
     "Only 50% of the requested quantity is covered, below the 90% minimum (covered: 500 of 1,000 L)."),
    ("P-04", may_contain_tree_nuts, SCHOOL,
     "Oat biscuit (400002) may contain tree nuts, which is excluded for Kilo School: Valio Aimo's data does not rule "
     "it out."),
    ("P-04", says_nothing_about_sesame, SCHOOL,
     "Oat biscuit (400002) says nothing about sesame seeds, which is excluded for Kilo School: Valio Aimo's data "
     "does not rule it out."),
    ("P-05", unlisted_same_category_substitute, SCHOOL,
     "Oat drink (471690) replaces Oddlygood Barista oat drink (473609), a substitute that Kilo School does not "
     "accept without a human."),
    ("P-06", sold_by_variable_weight, HOTEL,
     "Beef sirloin (400003) is sold by variable weight, so the total is an estimate: Valio Aimo invoices the weight "
     "delivered, which can be lower or higher than the weight ordered."),
    ("P-07", carries_a_deposit, HOTEL,
     "Mineral water 0.5 l (400004) carries a deposit that has no published price, so the total of €100.00 leaves it "
     "out."),
    ("P-08", renewal_at_twice_the_usual_quantity, HOTEL,
     "For the standing order “Weekly milk”, 200 L this week against a median of 100 L over the last 6 renewals, more "
     "than the 25% tolerance of Harbourside Hotel."),
    ("P-09", preferred_option_a_fifth_dearer, WARD,
     "This option is ranked by the preference of City Hospital, Ward 4 and costs €20.00 more before tax than the "
     "cheapest confirmed option, a premium of 20%, above the 10% a preference may add without a human."),
]


@pytest.fixture(scope="module")
def kits(
    engine: RulePolicyEngine, make_line: Callable, make_option: Callable, make_context: Callable,
    make_substitute: Callable, make_allergen_check: Callable, make_revalidation: Callable, now: Any,
) -> dict[str, Kit]:
    """One kit per shipped customer, each with ordering alone switched ON and nothing else changed."""
    return {
        customer: Kit(
            engine.get_profile(customer).model_copy(update={"auto_order_enabled": True}), make_line, make_option,
            make_context, make_substitute, make_allergen_check, make_revalidation, now,
        )
        for customer in CUSTOMERS
    }


def said(decision: PolicyDecision) -> str:
    """A decision as the table writes it."""
    if decision.verdict is Verdict.AUTO:
        return ALONE
    rules = ", ".join(dict.fromkeys(decision.rule_ids))
    if decision.verdict is Verdict.BLOCK:
        blocking = ", ".join(dict.fromkeys(rule.rule_id for rule in decision.fired if rule.verdict is Verdict.BLOCK))
        return f"NEVER {blocking}"
    return f"PERSON {rules} -> {', '.join(role.value for role in decision.required_roles)}"


def test_the_table_covers_every_shipped_customer_and_every_rule(engine: RulePolicyEngine) -> None:
    rule_ids = {rule.id for rule in load_rulebook(RULES_PATH).rules} | {"F-10"}

    assert set(CUSTOMERS) == set(load_profiles(PROFILES_DIR, frozenset())) == set(engine.profile_ids())
    assert all(set(expected) == set(CUSTOMERS) for _, expected in CASES)
    in_table = {rule for _, expected in CASES for outcome in expected.values() for rule in rule_ids if rule in outcome}
    assert in_table == rule_ids  # every rule decides at least one row
    assert {rule for rule, *_ in SENTENCES} == rule_ids  # and its sentence is read in full at least once


@pytest.mark.parametrize(("case", "expected"), CASES, ids=[case.__name__ for case, _ in CASES])
def test_what_the_agent_orders_alone_and_what_is_stopped(
    case: Callable[[Kit], Built], expected: dict[str, str], engine: RulePolicyEngine, kits: dict[str, Kit]
) -> None:
    decided = {}
    for customer, kit in kits.items():
        option, context = case(kit)
        decided[customer] = said(engine.evaluate(option, kit.profile, context))

    assert decided == expected


@pytest.mark.parametrize(
    ("rule_id", "case", "customer", "sentence"), SENTENCES,
    ids=[f"{rule}-{case.__name__}-{customer}" for rule, case, customer, _ in SENTENCES],
)
def test_the_sentence_the_person_reads(
    rule_id: str, case: Callable[[Kit], Built], customer: str, sentence: str, engine: RulePolicyEngine,
    kits: dict[str, Kit],
) -> None:
    kit = kits[customer]
    option, context = case(kit)

    decision = engine.evaluate(option, kit.profile, context)

    assert [rule.sentence for rule in decision.fired if rule.rule_id == rule_id] == [sentence]


def test_with_ordering_alone_off_the_same_table_never_lets_the_agent_order(
    engine: RulePolicyEngine, kits: dict[str, Kit]
) -> None:
    """The shipped setting: what the table calls ALONE goes to the purchasing manager under F-10, and nothing
    else moves: a NEVER stays a NEVER and a PERSON keeps its rules and roles."""
    for case, expected in CASES:
        for customer, kit in kits.items():
            option, context = case(kit)
            shipped = engine.get_profile(customer)

            decision = engine.evaluate(option, shipped, context)

            assert shipped.auto_order_enabled is False
            wanted = f"PERSON F-10 -> {PM}" if expected[customer] == ALONE else expected[customer]
            assert said(decision) == wanted, (case.__name__, customer)
