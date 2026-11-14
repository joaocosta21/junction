"""Buyer profiles: the shipped values, the schema, and the rule that no profile weakens a fixed rule."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from tta.contracts.common import (
    AllergenRelation,
    AllergenStrictness,
    ApproverRole,
    AvailabilityState,
    CheckResult,
    ClaimStatus,
    DepositRule,
    SubstitutionScope,
    VariableWeightRule,
    Verdict,
)
from tta.contracts.errors import NotAuthorised
from tta.contracts.policy import BuyerProfile
from tta.policy import PROFILES_DIR, RULES_PATH, PolicyLoadError, RulePolicyEngine, load_profile, load_profiles

FIXED_IDS = frozenset({"F-01", "F-02", "F-03", "F-04", "F-05", "F-06", "F-07", "F-08", "F-09"})


def test_the_two_shipped_profiles_load(engine: RulePolicyEngine) -> None:
    assert engine.profile_ids() == ("allergy-ward", "hotel-kitchen")


def test_hotel_kitchen_carries_the_values_of_the_spec_and_is_marked_illustrative(hotel: BuyerProfile) -> None:
    assert hotel.illustrative is True
    assert "llustrative" in (hotel.description or "")
    assert hotel.auto_order_enabled is True
    assert hotel.max_order_net_eur == Decimal(750)
    assert hotel.max_daily_net_eur == Decimal(3000)
    assert hotel.min_fill_ratio == Decimal("0.9")
    assert hotel.excluded_allergens == () and hotel.allergen_strictness is None
    assert hotel.substitution_without_approval is SubstitutionScope.SAME_CATEGORY
    assert hotel.variable_weight is VariableWeightRule.APPROVAL
    assert hotel.deposits is DepositRule.APPROVAL
    assert hotel.require_confirmed is False
    assert hotel.approver_roles[ApproverRole.PURCHASING_MANAGER] == ("human:hotel-purchasing",)
    assert hotel.approver_roles[ApproverRole.FINANCE] == ("human:hotel-finance",)


def test_allergy_ward_carries_the_values_of_the_spec_and_is_marked_illustrative(ward: BuyerProfile) -> None:
    assert ward.illustrative is True
    assert "llustrative" in (ward.description or "")
    assert ward.auto_order_enabled is True
    assert ward.max_order_net_eur == Decimal(500)
    assert ward.max_daily_net_eur == Decimal(1500)
    assert ward.min_fill_ratio == Decimal(1)
    assert ward.excluded_allergens == ("AM", "AW")
    assert ward.allergen_strictness is AllergenStrictness.STRICT
    assert ward.substitution_without_approval is SubstitutionScope.NONE
    assert ward.require_confirmed is True
    assert ward.approver_roles[ApproverRole.DIETITIAN] == ("human:ward-dietitian",)


def test_the_shipped_files_say_illustrative_where_a_person_reads_them() -> None:
    for path in sorted(PROFILES_DIR.glob("*.yaml")):
        assert "ILLUSTRATIVE" in path.read_text(encoding="utf-8").splitlines()[0], path.name


def test_an_unknown_profile_is_not_authorised(engine: RulePolicyEngine) -> None:
    with pytest.raises(NotAuthorised):
        engine.get_profile("somebody-else")


@pytest.mark.parametrize(
    "attempt",
    [
        {"F-01": "off"},
        {"rules": {"F-01": {"enabled": False}}},
        {"disabled_rules": ["F-02"]},
        {"overrides": [{"rule": "f-03", "verdict": "AUTO"}]},
        {"fixed_rules": {"F-04": False, "F-05": False}},
        {"F-06": False},
        {"switched_off": ["f-07"]},
        {"substitutes": {"F-08": False}},
    ],
    ids=["top-level key", "nested key", "list item", "lower-case value", "two rules", "access rule", "F-07", "F-08"],
)
def test_a_profile_that_touches_a_fixed_rule_is_rejected_at_load(
    attempt: dict[str, Any], profile_data: Callable[[str], dict[str, Any]], write_yaml: Callable[[str, Any], Path],
) -> None:
    path = write_yaml("hotel-kitchen.yaml", {**profile_data("hotel-kitchen"), **attempt})

    with pytest.raises(PolicyLoadError, match="fixed rule"):
        load_profile(path, FIXED_IDS)


def test_the_engine_refuses_to_start_with_a_profile_that_switches_a_fixed_rule_off(
    profile_data: Callable[[str], dict[str, Any]], write_yaml: Callable[[str, Any], Path], tmp_path: Path,
) -> None:
    write_yaml("profiles/hotel-kitchen.yaml", {**profile_data("hotel-kitchen"), "F-01": "off"})

    with pytest.raises(PolicyLoadError, match="F-01"):
        RulePolicyEngine.from_files(RULES_PATH, tmp_path / "profiles")


def test_a_profile_that_lists_exclusions_without_a_strictness_is_rejected_at_load(
    profile_data: Callable[[str], dict[str, Any]], write_yaml: Callable[[str, Any], Path],
) -> None:
    data = profile_data("allergy-ward")
    del data["allergen_strictness"]

    with pytest.raises(PolicyLoadError, match="allergen_strictness"):
        load_profile(write_yaml("allergy-ward.yaml", data), FIXED_IDS)


def test_the_engine_refuses_to_start_with_a_profile_that_names_f07(
    profile_data: Callable[[str], dict[str, Any]], write_yaml: Callable[[str, Any], Path], tmp_path: Path,
) -> None:
    """The ids no profile may name come from the rules file itself, so the new fixed rule is covered."""
    write_yaml("profiles/hotel-kitchen.yaml", {**profile_data("hotel-kitchen"), "price_checks": {"F-07": "off"}})

    with pytest.raises(PolicyLoadError, match="names fixed rule F-07"):
        RulePolicyEngine.from_files(RULES_PATH, tmp_path / "profiles")


@pytest.mark.parametrize(
    ("codes", "message"),
    [
        (["milk", "am"], "excluded_allergens: unknown allergen code 'milk', 'am':"),
        (["AM", "ZZ"], "excluded_allergens: unknown allergen code 'ZZ':"),
        (["AM "], "excluded_allergens: unknown allergen code 'AM ':"),  # quoted, so that the blank shows
        (["X99"], "excluded_allergens: X99 is the general statement"),
        (["AM", "X99"], "not an allergen that can be excluded"),
    ],
    ids=["words and lower case", "one unknown code", "a blank after the code", "X99", "X99 next to a real code"],
)
def test_a_profile_that_excludes_something_that_is_not_an_allergen_code_is_rejected_at_load(
    codes: list[str], message: str, profile_data: Callable[[str], dict[str, Any]],
    write_yaml: Callable[[str, Any], Path],
) -> None:
    data = {**profile_data("hotel-kitchen"), "excluded_allergens": codes, "allergen_strictness": "STRICT"}

    with pytest.raises(PolicyLoadError) as raised:
        load_profile(write_yaml("hotel-kitchen.yaml", data), FIXED_IDS)

    assert message in str(raised.value)


def test_every_problem_with_the_exclusion_codes_of_a_profile_is_reported_at_once(
    profile_data: Callable[[str], dict[str, Any]], write_yaml: Callable[[str, Any], Path],
) -> None:
    data = {**profile_data("hotel-kitchen"), "excluded_allergens": ["milk", "X99"], "allergen_strictness": "STRICT"}

    with pytest.raises(PolicyLoadError) as raised:
        load_profile(write_yaml("hotel-kitchen.yaml", data), FIXED_IDS)

    assert len(raised.value.problems) == 2


def test_a_profile_that_excludes_known_allergen_codes_loads(
    profile_data: Callable[[str], dict[str, Any]], write_yaml: Callable[[str, Any], Path],
) -> None:
    data = {**profile_data("hotel-kitchen"), "excluded_allergens": ["AP", "GO"], "allergen_strictness": "DECLARED_ONLY"}

    assert load_profile(write_yaml("hotel-kitchen.yaml", data), FIXED_IDS).excluded_allergens == ("AP", "GO")


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"rules": {"P-01": "off"}}, "unknown setting"),
        ({"max_order_net_eur": -1}, "max_order_net_eur"),
        ({"min_fill_ratio": 1.5}, "min_fill_ratio"),
        ({"substitution_without_approval": "ANYTHING"}, "substitution_without_approval"),
        ({"approver_roles": {"janitor": ["human:x"]}}, "approver_roles"),
        ({"profile_id": "other-name"}, "file name"),
    ],
    ids=["rule section", "negative limit", "ratio above one", "unknown scope", "unknown role", "id and file differ"],
)
def test_a_profile_outside_the_schema_is_rejected_at_load(
    change: dict[str, Any], message: str, profile_data: Callable[[str], dict[str, Any]],
    write_yaml: Callable[[str, Any], Path],
) -> None:
    path = write_yaml("hotel-kitchen.yaml", {**profile_data("hotel-kitchen"), **change})

    with pytest.raises(PolicyLoadError, match=message):
        load_profile(path, FIXED_IDS)


def test_a_profile_with_a_missing_setting_is_rejected_at_load(
    profile_data: Callable[[str], dict[str, Any]], write_yaml: Callable[[str, Any], Path],
) -> None:
    data = profile_data("hotel-kitchen")
    del data["max_daily_net_eur"]

    with pytest.raises(PolicyLoadError, match="max_daily_net_eur"):
        load_profile(write_yaml("hotel-kitchen.yaml", data), FIXED_IDS)


@pytest.mark.parametrize("content", ["- just\n- a list\n", "", "profile_id: [unclosed\n"])
def test_a_file_that_is_not_a_profile_is_rejected_at_load(content: str, tmp_path: Path) -> None:
    path = tmp_path / "broken.yaml"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(PolicyLoadError):
        load_profile(path, FIXED_IDS)


def test_a_folder_without_profiles_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(PolicyLoadError, match="no buyer profile"):
        load_profiles(tmp_path, FIXED_IDS)


def test_load_profiles_returns_every_profile_by_id() -> None:
    profiles = load_profiles(PROFILES_DIR, FIXED_IDS)

    assert sorted(profiles) == ["allergy-ward", "hotel-kitchen"]
    assert all(profile.profile_id == profile_id for profile_id, profile in profiles.items())


# --- no setting of a profile reaches a fixed rule ------------------------------------------------------------

@pytest.fixture
def permissive(hotel: BuyerProfile) -> BuyerProfile:
    """Every setting at its most permissive value: the most a profile file can ask for."""
    return hotel.model_copy(update={
        "auto_order_enabled": True,
        "max_order_net_eur": Decimal(10**9),
        "max_daily_net_eur": Decimal(10**9),
        "min_fill_ratio": Decimal(0),
        "excluded_allergens": (),
        "allergen_strictness": None,
        "substitution_without_approval": SubstitutionScope.SAME_CATEGORY,
        "variable_weight": VariableWeightRule.AUTO_WITH_CEILING,
        "deposits": DepositRule.NOTE,
        "require_confirmed": False,
    })


def test_the_most_permissive_profile_orders_alone_only_what_no_fixed_rule_catches(
    engine: RulePolicyEngine, permissive: BuyerProfile, make_line: Callable, make_option: Callable,
    make_context: Callable,
) -> None:
    lines = (make_line(variable_weight=True, has_deposits=True),)
    option = make_option(lines, net="250000.00", fill_ratio="0.1", is_ceiling=True, excludes_deposits=True)

    assert engine.evaluate(option, permissive, make_context(day_committed="900000")).verdict is Verdict.AUTO


@pytest.mark.parametrize("needed_by", [CheckResult.NOT_MET, CheckResult.UNVERIFIED])
def test_the_most_permissive_profile_cannot_order_alone_past_a_needed_by_date(
    needed_by: CheckResult, engine: RulePolicyEngine, permissive: BuyerProfile, make_option: Callable,
    make_context: Callable,
) -> None:
    decision = engine.evaluate(make_option(needed_by=needed_by), permissive, make_context())

    assert decision.rule_ids == ("F-07",) and decision.verdict is Verdict.APPROVAL and decision.fired[0].fixed


@pytest.mark.parametrize("case", ["F-01", "F-02", "F-03", "F-04", "F-05", "F-07", "F-08"])
def test_the_most_permissive_profile_cannot_switch_off_a_fixed_rule(
    case: str, engine: RulePolicyEngine, permissive: BuyerProfile, make_line: Callable, make_option: Callable,
    make_context: Callable, make_allergen_check: Callable, make_substitute: Callable, make_revalidation: Callable,
) -> None:
    line: dict[str, Any] = {}
    context: dict[str, Any] = {}
    if case == "F-01":
        line["state"] = AvailabilityState.QUANTITY_NOT_CONFIRMED
    elif case == "F-02":  # an exclusion that came with the request
        line["allergen_check"] = make_allergen_check({"AP": AllergenRelation.CONTAINS})
    elif case == "F-03":
        line["variable_weight"] = None
    elif case == "F-04":
        context = {"at_order_time": True, "revalidation": make_revalidation(ok=False, changed_price=True)}
    elif case == "F-07":
        line["price_claim"] = ClaimStatus.UNKNOWN
    elif case == "F-08":
        line["substitute"] = make_substitute(claims_lost=("FREE_FROM_LACTOSE",))
    else:
        line["substitute"] = make_substitute(added=(("AW", AllergenRelation.CONTAINS),))

    decision = engine.evaluate(make_option((make_line(**line),)), permissive, make_context(**context))

    assert decision.rule_ids == (case,)
    assert decision.verdict is not Verdict.AUTO
    assert decision.fired[0].fixed
