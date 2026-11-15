"""A sentence names who really decides at that customer (decision B54: one person confirms).

The hotel's and the bakery's person who orders holds every role; at the ward and the school that person also holds
finance's, and the dietitian is the only second person. No customer has a separate finance signer. So "the order
goes to finance" and "it needs the dietitian" named somebody who is not there: the authority and the decision now
say the purchasing manager wherever everybody who holds the role is the person who orders. The role a rule asks
for is unchanged in the data (`approver_role`, `required_roles`): only the words follow the customer.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from tta.contracts.common import AllergenRelation, AllergenStrictness, ApproverRole, Verdict
from tta.contracts.offer import OfferLine, OfferOption
from tta.contracts.policy import BuyerProfile, PolicyContext
from tta.policy import RULES_PATH, RulePolicyEngine, load_rulebook
from tta.policy.human_approval import (
    ROLE_NAMES,
    decided_as,
    dietitian_is_second_person,
    has_own,
    roles_said,
    several_can_sign,
)

PM, DIETITIAN, FINANCE = ApproverRole.PURCHASING_MANAGER, ApproverRole.DIETITIAN, ApproverRole.FINANCE
ONE_PERSON = ("hotel-kitchen", "bakery-cafe")
WITH_A_DIETITIAN = ("allergy-ward", "school-kitchen")


def _sentence(engine: RulePolicyEngine, profile: BuyerProfile, rule_id: str) -> str:
    return next(rule.sentence for rule in engine.describe_authority(profile).rules if rule.rule_id == rule_id)


@pytest.mark.parametrize("profile_id", ONE_PERSON)
def test_where_one_person_holds_every_role_every_question_is_the_purchasing_managers(
    profile_id: str, engine: RulePolicyEngine
) -> None:
    profile = engine.get_profile(profile_id)

    assert not several_can_sign(profile)
    assert not has_own(profile, DIETITIAN) and not has_own(profile, FINANCE)
    assert [decided_as(profile, role) for role in (PM, DIETITIAN, FINANCE)] == [PM, PM, PM]
    assert roles_said((PM, DIETITIAN, FINANCE), profile) == "the purchasing manager"


@pytest.mark.parametrize("profile_id", WITH_A_DIETITIAN)
def test_where_a_dietitian_is_a_second_person_her_questions_stay_hers_and_finance_is_the_purchasing_managers(
    profile_id: str, engine: RulePolicyEngine
) -> None:
    profile = engine.get_profile(profile_id)

    assert several_can_sign(profile)
    assert has_own(profile, DIETITIAN) and not has_own(profile, FINANCE)
    assert [decided_as(profile, role) for role in (PM, DIETITIAN, FINANCE)] == [PM, DIETITIAN, PM]
    assert roles_said((PM, DIETITIAN, FINANCE), profile) == "the purchasing manager and the dietitian"
    assert roles_said((FINANCE,), profile) == "the purchasing manager"


def test_a_role_nobody_holds_keeps_its_own_name_so_the_gap_is_seen(hotel: BuyerProfile) -> None:
    roles = {role: ids for role, ids in hotel.approver_roles.items() if role is not DIETITIAN}
    no_dietitian = hotel.model_copy(update={"approver_roles": roles})
    own_finance = hotel.model_copy(update={"approver_roles": {**hotel.approver_roles, FINANCE: ("human:cfo",)}})

    assert decided_as(no_dietitian, DIETITIAN) is DIETITIAN and not has_own(no_dietitian, DIETITIAN)
    assert decided_as(own_finance, FINANCE) is FINANCE and has_own(own_finance, FINANCE)
    assert roles_said((PM, FINANCE), own_finance) == "the purchasing manager and finance"


def test_the_dietitian_is_the_second_person_at_the_ward_and_the_school_and_nowhere_else(
    engine: RulePolicyEngine, hotel: BuyerProfile
) -> None:
    """Rules F-11 and F-12 follow this shape (decision B66), not "somebody holds the dietitian's role"."""
    second = {  # the four customers by name: another lane may add a profile file of its own
        profile_id: dietitian_is_second_person(engine.get_profile(profile_id))
        for profile_id in (*WITH_A_DIETITIAN, *ONE_PERSON)
    }
    one_per_role = hotel.model_copy(update={"approver_roles": {
        PM: ("human:my-kitchen-purchasing",), FINANCE: ("human:my-kitchen-finance",),
        DIETITIAN: ("human:my-kitchen-dietitian",),
    }})
    nobody = hotel.model_copy(update={"approver_roles": {}})

    assert second == {"allergy-ward": True, "school-kitchen": True, "hotel-kitchen": False, "bakery-cafe": False}
    # A demo book of the shop page lists one approver per role, each standing for the customer's one person: it
    # is not read as a customer with a dietitian of its own, so the hotel's book never asks one.
    assert has_own(one_per_role, DIETITIAN) and not dietitian_is_second_person(one_per_role)
    assert not dietitian_is_second_person(nobody)


def test_in_a_book_with_one_approver_per_role_a_substitute_that_is_not_like_for_like_stays_with_the_purchasing_manager(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
    make_substitute: Callable[..., Any],
) -> None:
    from tta.contracts.product import ReplaceCheck, ReplaceVerdict

    book = hotel.model_copy(update={"approver_roles": {
        PM: ("human:my-kitchen-purchasing",), FINANCE: ("human:my-kitchen-finance",),
        DIETITIAN: ("human:my-kitchen-dietitian",),
    }})
    check = ReplaceCheck(
        verdict=ReplaceVerdict.NOT_LIKE_FOR_LIKE, reasons=("not made for coffee, as the product asked for is",),
        sentence="Not a like-for-like replacement: not made for coffee, as the product asked for is.",
    )
    line = make_line("473424", "Alpro Rice drink 1L", substitute=make_substitute(listed=False, replaceable=check))

    decision = engine.evaluate(make_option((line,)), book, make_context())

    assert decision.rule_ids == ("F-12",) and decision.required_roles == (PM,)
    assert decision.fired[0].facts["profile.dietitian_is_second_person"] is False
    assert decision.sentence.endswith("(F-12). It needs the purchasing manager.")


def test_the_role_names_are_those_of_the_rules_file() -> None:
    roles = load_rulebook(RULES_PATH).roles

    assert {role: spec.name for role, spec in roles.items()} == dict(ROLE_NAMES)


# --- the authority (GET /v1/authority) ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("profile_id", "limit"),
    [("hotel-kitchen", "3,000"), ("bakery-cafe", "1,000"), ("allergy-ward", "1,500"), ("school-kitchen", "800")],
)
def test_no_customer_has_a_finance_signer_so_a_spend_stop_goes_to_the_purchasing_manager(
    profile_id: str, limit: str, engine: RulePolicyEngine
) -> None:
    profile = engine.get_profile(profile_id)

    assert _sentence(engine, profile, "P-02") == (
        f"When the day's orders, this one included, pass €{limit} before tax, the order goes to the purchasing "
        "manager."
    )
    assert _sentence(engine, profile, "P-07").startswith(
        "A product that carries a deposit goes to the purchasing manager:"
    )
    said = " ".join(rule.sentence for rule in engine.describe_authority(profile).rules)
    assert "finance" not in said, profile_id


def test_a_customer_with_a_finance_signer_of_its_own_still_reads_finance(
    engine: RulePolicyEngine, hotel: BuyerProfile
) -> None:
    own_finance = hotel.model_copy(update={"approver_roles": {**hotel.approver_roles, FINANCE: ("human:cfo",)}})

    assert _sentence(engine, own_finance, "P-02") == (
        "When the day's orders, this one included, pass €3,000 before tax, the order goes to finance."
    )
    assert _sentence(engine, own_finance, "P-07").startswith("A product that carries a deposit goes to finance:")


@pytest.mark.parametrize(
    ("profile_id", "who"),
    [
        ("hotel-kitchen", "the purchasing manager"), ("bakery-cafe", "the purchasing manager"),
        ("allergy-ward", "the dietitian"), ("school-kitchen", "the dietitian"),
    ],
)
def test_the_authority_names_the_dietitian_only_where_the_customer_has_one(
    profile_id: str, who: str, engine: RulePolicyEngine
) -> None:
    profile = engine.get_profile(profile_id)
    said = {rule.rule_id: rule.sentence for rule in engine.describe_authority(profile).rules}

    for rule_id in ("P-04", "F-08", "F-11", "F-12"):
        assert f"goes to {who}" in said[rule_id], (rule_id, said[rule_id])
    if who != "the dietitian":
        assert "dietitian" not in " ".join(said.values()), profile_id
    # The role each rule asks for is unchanged where it was the dietitian's already.
    rules = {rule.rule_id: rule for rule in engine.describe_authority(profile).rules}
    assert rules["P-04"].approver_role is DIETITIAN and rules["P-02"].approver_role is FINANCE


# --- the decision ---------------------------------------------------------------------------------------------


def test_an_allergen_doubt_at_the_hotel_needs_the_purchasing_manager_and_at_the_ward_the_dietitian(
    engine: RulePolicyEngine, hotel: BuyerProfile, ward: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
    make_allergen_check: Callable[..., Any],
) -> None:
    """The page's own example: "100 litres of Elovena barista oat drink, product 469512, by Monday; no milk"."""
    doubt = make_allergen_check({"AM": AllergenRelation.NOT_STATED, "AW": AllergenRelation.FREE_FROM})
    line = make_line("469512", "Elovena Barista oat drink", allergen_check=doubt)
    asks_no_milk = hotel.model_copy(
        update={"excluded_allergens": ("AM", "AW"), "allergen_strictness": AllergenStrictness.STRICT}
    )

    at_the_hotel = engine.evaluate(make_option((line,)), asks_no_milk, make_context())
    at_the_ward = engine.evaluate(make_option((line,)), ward, make_context())

    for decision in (at_the_hotel, at_the_ward):  # the same rule and the same role in the data
        assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("P-04",)
        assert decision.required_roles == (DIETITIAN,)
    assert at_the_hotel.sentence.endswith("(P-04). It needs the purchasing manager.")
    assert at_the_ward.sentence.endswith("(P-04). It needs the dietitian.")


def test_a_day_limit_stop_needs_the_purchasing_manager_and_names_nobody_twice(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(make_option(net="800.00"), hotel, make_context(day_committed="2500"))

    assert decision.rule_ids == ("P-01", "P-02")
    assert decision.required_roles == (PM, FINANCE)  # the roles asked, as before: one person holds both
    assert decision.sentence.endswith("(P-02). It needs the purchasing manager.")


# --- a missing line is not a late date (rule F-07 for the option) ---------------------------------------------


def test_an_option_that_leaves_a_request_line_out_says_so_and_does_not_call_the_date_late(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    """The menu planner's order: every product offered is in time, and nothing is offered for one request line.
    The offer's needed-by check is then NOT_MET ("the request is not delivered in full by the date")."""
    from decimal import Decimal

    from tta.contracts.common import CheckResult, Unit
    from tta.contracts.offer import Coverage

    full = make_option((make_line(),), needed_by=CheckResult.NOT_MET, fill_ratio="0")
    covered = Coverage(request_line_index=0, requested=Decimal(100), covered=Decimal(100), unit=Unit.L,
                       fill_ratio=Decimal(1), missing=Decimal(0))
    left_out = Coverage(request_line_index=1, requested=Decimal(2), covered=Decimal(0), unit=Unit.KG,
                        fill_ratio=Decimal(0), missing=Decimal(2))
    option = full.model_copy(update={"coverage": (covered, left_out)})

    decision = engine.evaluate(option, hotel, make_context())

    f07 = next(rule for rule in decision.fired if rule.rule_id == "F-07")
    assert f07.sentence == "Nothing is offered for request line 2; what is offered arrives by Monday 16 Nov."
    p03 = next(rule for rule in decision.fired if rule.rule_id == "P-03")
    assert p03.sentence == (
        "1 of the 2 items asked for are covered in full; nothing is offered for request line 2; Harbourside Hotel "
        "asks for at least 90% of every item."
    )
    assert "is not met" not in decision.sentence and "only 0%" not in decision.sentence


def test_a_late_product_still_reads_as_a_date_that_is_not_met(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    from tta.contracts.common import CheckResult, ClaimStatus

    late = make_line(delivery_date_claim=ClaimStatus.RULED_OUT)

    decision = engine.evaluate(make_option((late,), needed_by=CheckResult.NOT_MET), hotel, make_context())

    # Said once, by the option's entry, with the product named and no "ruled out".
    assert [(rule.rule_id, rule.product_id, rule.sentence) for rule in decision.fired] == [(
        "F-07", None,
        "The needed-by date 2026-11-16 is not met for this option: Arla Café milk 1 L UHT (463380) cannot be "
        "delivered by then.",
    )]
