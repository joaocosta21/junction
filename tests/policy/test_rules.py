"""Each rule of SPEC section 7 fires when its condition holds and stays silent when it does not."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from tta.contracts.common import (
    AllergenOutcome,
    AllergenRelation,
    AllergenStrictness,
    ApproverRole,
    AvailabilityState,
    ClaimStatus,
    DepositRule,
    SubstitutionScope,
    VariableWeightRule,
    Verdict,
)
from tta.contracts.offer import OfferLine, OfferOption
from tta.contracts.policy import BuyerProfile, FiredRule, PolicyContext, PolicyDecision
from tta.policy import RulePolicyEngine

NOT_CONFIRMED_STATES = [state for state in AvailabilityState if state is not AvailabilityState.CONFIRMED]


def _fired(decision: PolicyDecision, rule_id: str) -> FiredRule:
    return next(rule for rule in decision.fired if rule.rule_id == rule_id)


def test_a_plain_confirmed_order_within_every_limit_fires_nothing(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(make_option(), hotel, make_context())

    assert decision.verdict is Verdict.AUTO and decision.fired == ()


# --- F-01 ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("state", NOT_CONFIRMED_STATES)
def test_f01_fires_for_every_state_other_than_confirmed(
    state: AvailabilityState, engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    option = make_option((make_line(state=state, quantity_claim=None),))

    decision = engine.evaluate(option, hotel, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-01",)
    assert _fired(decision, "F-01").facts["line.availability_state"] == state.value


def test_f01_fires_when_the_state_is_confirmed_but_the_quantity_claim_is_not(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    option = make_option((make_line(quantity_claim=ClaimStatus.UNKNOWN),))

    assert engine.evaluate(option, hotel, make_context()).rule_ids == ("F-01",)


def test_f01_is_silent_for_a_confirmed_line_and_names_each_unconfirmed_one(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    lines = (
        make_line("463380"),
        make_line("464306", "Milk drink", state=AvailabilityState.QUANTITY_NOT_CONFIRMED),
        make_line("469363", "Other milk", state=AvailabilityState.QUANTITY_NOT_CONFIRMED),
    )

    decision = engine.evaluate(make_option(lines), hotel, make_context())

    assert [(rule.rule_id, rule.product_id) for rule in decision.fired] == [("F-01", "464306"), ("F-01", "469363")]


# --- F-02 and P-04 ------------------------------------------------------------------------------------------

def test_f02_blocks_a_line_that_declares_an_excluded_allergen(
    engine: RulePolicyEngine, ward: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
    make_allergen_check: Callable,
) -> None:
    check = make_allergen_check({"AM": AllergenRelation.CONTAINS, "AW": AllergenRelation.FREE_FROM})

    decision = engine.evaluate(make_option((make_line(allergen_check=check),)), ward, make_context())

    assert decision.verdict is Verdict.BLOCK and decision.rule_ids == ("F-02",)
    f02 = _fired(decision, "F-02")
    assert f02.fixed and f02.approver_role is None and f02.product_id == "463380"
    assert f02.facts["line.allergens_declared"] == ["AM (contains)"]


def test_f02_blocks_when_one_finding_rejects_even_if_the_check_as_a_whole_says_pass(
    engine: RulePolicyEngine, ward: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
    make_allergen_check: Callable,
) -> None:
    inconsistent = make_allergen_check(
        {"AM": AllergenRelation.CONTAINS, "AW": AllergenRelation.FREE_FROM}, outcome=AllergenOutcome.PASS
    )

    decision = engine.evaluate(make_option((make_line(allergen_check=inconsistent),)), ward, make_context())

    assert decision.verdict is Verdict.BLOCK and decision.rule_ids == ("F-02",)


def test_f02_and_p04_are_silent_when_every_excluded_allergen_is_free_from(
    engine: RulePolicyEngine, ward: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
    make_allergen_check: Callable,
) -> None:
    check = make_allergen_check({"AM": AllergenRelation.FREE_FROM, "AW": AllergenRelation.FREE_FROM})

    decision = engine.evaluate(make_option((make_line(allergen_check=check),)), ward, make_context())

    assert decision.verdict is Verdict.AUTO


@pytest.mark.parametrize(
    "relation", [AllergenRelation.MAY_CONTAIN, AllergenRelation.UNDECLARED, AllergenRelation.NOT_STATED]
)
def test_p04_sends_an_allergen_that_is_not_ruled_out_to_the_dietitian(
    relation: AllergenRelation, engine: RulePolicyEngine, ward: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
    make_allergen_check: Callable,
) -> None:
    check = make_allergen_check({"AM": AllergenRelation.FREE_FROM, "AW": relation})

    decision = engine.evaluate(make_option((make_line(allergen_check=check),)), ward, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("P-04",)
    assert decision.required_roles == (ApproverRole.DIETITIAN,)
    assert not _fired(decision, "P-04").fixed


def test_p04_fires_when_one_finding_asks_for_a_human_even_if_the_check_as_a_whole_says_pass(
    engine: RulePolicyEngine, ward: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
    make_allergen_check: Callable,
) -> None:
    inconsistent = make_allergen_check(
        {"AM": AllergenRelation.MAY_CONTAIN, "AW": AllergenRelation.FREE_FROM}, outcome=AllergenOutcome.PASS
    )

    decision = engine.evaluate(make_option((make_line(allergen_check=inconsistent),)), ward, make_context())

    assert decision.rule_ids == ("P-04",)
    assert _fired(decision, "P-04").facts["line.allergens_to_human"] == ["AM (may contain)"]
    assert _fired(decision, "P-04").sentence == (
        "Arla Café milk 1 L UHT (463380) does not rule out an allergen this buyer excludes: AM (may contain)."
    )


def test_p04_applies_to_exclusions_that_came_with_the_request_of_a_profile_without_any(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
    make_allergen_check: Callable,
) -> None:
    lenient = make_allergen_check({"AP": AllergenRelation.NOT_STATED}, strictness=AllergenStrictness.DECLARED_ONLY)
    strict = make_allergen_check({"AP": AllergenRelation.NOT_STATED}, strictness=AllergenStrictness.STRICT)

    passes = engine.evaluate(make_option((make_line(allergen_check=lenient),)), hotel, make_context())
    to_human = engine.evaluate(make_option((make_line(allergen_check=strict),)), hotel, make_context())

    assert passes.verdict is Verdict.AUTO  # DECLARED_ONLY: no statement passes, shown as unverified
    assert to_human.rule_ids == ("P-04",)


# --- F-05 and P-05 ------------------------------------------------------------------------------------------

def test_f05_blocks_a_substitute_that_adds_an_allergen(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext], make_substitute: Callable,
) -> None:
    substitute = make_substitute(added=(("AW", AllergenRelation.CONTAINS),))
    option = make_option((make_line("471881", "Oat drink gluten-free", substitute=substitute),))

    decision = engine.evaluate(option, hotel, make_context())

    assert decision.verdict is Verdict.BLOCK and decision.rule_ids == ("F-05",)
    f05 = _fired(decision, "F-05")
    assert f05.fixed and f05.product_id == "471881"
    assert f05.sentence == (
        "Oat drink gluten-free (471881) would replace Oddlygood Barista oat drink (473609) but adds an allergen "
        "the original does not declare: AW (contains)."
    )


def test_f05_is_silent_for_a_substitute_that_adds_no_allergen(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext], make_substitute: Callable,
) -> None:
    option = make_option((make_line("471690", "Oat drink", substitute=make_substitute()),))

    assert engine.evaluate(option, hotel, make_context()).verdict is Verdict.AUTO


@pytest.mark.parametrize(
    ("scope", "listed", "distance", "fires"),
    [
        (SubstitutionScope.NONE, True, 0, True),
        (SubstitutionScope.LISTED_BY_SUPPLIER, True, 0, False),
        (SubstitutionScope.LISTED_BY_SUPPLIER, True, 2, False),
        (SubstitutionScope.LISTED_BY_SUPPLIER, False, 0, True),
        (SubstitutionScope.SAME_CATEGORY, False, 0, False),
        (SubstitutionScope.SAME_CATEGORY, True, 1, False),
        (SubstitutionScope.SAME_CATEGORY, False, 1, True),
        (SubstitutionScope.SAME_CATEGORY, False, 2, True),
    ],
)
def test_p05_sends_a_substitute_outside_the_profile_scope_to_the_purchasing_manager(
    scope: SubstitutionScope, listed: bool, distance: int, fires: bool, engine: RulePolicyEngine,
    hotel: BuyerProfile, make_line: Callable[..., OfferLine], make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext], make_substitute: Callable,
) -> None:
    profile = hotel.model_copy(update={"substitution_without_approval": scope})
    substitute = make_substitute(listed=listed, category_distance=distance)
    option = make_option((make_line("471690", "Oat drink", substitute=substitute),))

    decision = engine.evaluate(option, profile, make_context())

    assert decision.rule_ids == (("P-05",) if fires else ())
    if fires:
        assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)


def test_p05_is_silent_for_a_line_that_replaces_nothing(
    engine: RulePolicyEngine, ward: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
    make_allergen_check: Callable,
) -> None:
    check = make_allergen_check({"AM": AllergenRelation.FREE_FROM, "AW": AllergenRelation.FREE_FROM})

    decision = engine.evaluate(make_option((make_line(allergen_check=check),)), ward, make_context())

    assert ward.substitution_without_approval is SubstitutionScope.NONE and decision.fired == ()


# --- P-00 to P-03 -------------------------------------------------------------------------------------------

def test_p00_sends_every_order_to_a_human_when_the_profile_switches_auto_ordering_off(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    profile = hotel.model_copy(update={"auto_order_enabled": False})

    decision = engine.evaluate(make_option(), profile, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("P-00",)
    assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)


@pytest.mark.parametrize(("net", "fires"), [("750.00", False), ("750.01", True), ("749.99", False)])
def test_p01_fires_only_above_the_limit_per_order(
    net: str, fires: bool, engine: RulePolicyEngine, hotel: BuyerProfile, make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    assert engine.evaluate(make_option(net=net), hotel, make_context()).rule_ids == (("P-01",) if fires else ())


@pytest.mark.parametrize(("committed", "fires"), [("2900.00", False), ("2900.01", True), ("0", False)])
def test_p02_fires_only_when_the_day_with_this_order_passes_the_limit_per_day(
    committed: str, fires: bool, engine: RulePolicyEngine, hotel: BuyerProfile,
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(make_option(net="100.00"), hotel, make_context(day_committed=committed))

    assert decision.rule_ids == (("P-02",) if fires else ())
    if fires:
        assert decision.required_roles == (ApproverRole.FINANCE,)


@pytest.mark.parametrize(("fill", "fires"), [("0.9", False), ("0.8999", True), ("1", False), ("0", True)])
def test_p03_fires_only_below_the_minimum_fill_ratio(
    fill: str, fires: bool, engine: RulePolicyEngine, hotel: BuyerProfile, make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(make_option(fill_ratio=fill), hotel, make_context())

    assert decision.rule_ids == (("P-03",) if fires else ())


# --- P-06 and P-07 ------------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("variable", "setting", "is_ceiling", "fires"),
    [
        (True, VariableWeightRule.APPROVAL, True, True),
        (True, VariableWeightRule.APPROVAL, False, True),
        (True, VariableWeightRule.AUTO_WITH_CEILING, True, False),
        (True, VariableWeightRule.AUTO_WITH_CEILING, False, True),
        (False, VariableWeightRule.APPROVAL, False, False),
    ],
)
def test_p06_variable_weight_follows_the_profile_setting(
    variable: bool, setting: VariableWeightRule, is_ceiling: bool, fires: bool, engine: RulePolicyEngine,
    hotel: BuyerProfile, make_line: Callable[..., OfferLine], make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    profile = hotel.model_copy(update={"variable_weight": setting})
    option = make_option((make_line("464744", "Beef chuck", variable_weight=variable),), is_ceiling=is_ceiling)

    decision = engine.evaluate(option, profile, make_context())

    assert decision.rule_ids == (("P-06",) if fires else ())
    if fires:
        assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)


@pytest.mark.parametrize(
    ("deposits", "setting", "excludes_deposits", "fires"),
    [
        (True, DepositRule.APPROVAL, True, True),
        (True, DepositRule.NOTE, True, False),
        (True, DepositRule.NOTE, False, True),
        (False, DepositRule.APPROVAL, False, False),
    ],
)
def test_p07_deposits_follow_the_profile_setting(
    deposits: bool, setting: DepositRule, excludes_deposits: bool, fires: bool, engine: RulePolicyEngine,
    hotel: BuyerProfile, make_line: Callable[..., OfferLine], make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    profile = hotel.model_copy(update={"deposits": setting})
    option = make_option((make_line(has_deposits=deposits),), excludes_deposits=excludes_deposits)

    decision = engine.evaluate(option, profile, make_context())

    assert decision.rule_ids == (("P-07",) if fires else ())
    if fires:
        assert decision.required_roles == (ApproverRole.FINANCE,)
