"""The four shipped buyer profiles: one per customer of the demonstration (runbook, "Four customers, one definition").

Limits, the allergen rule, the substitution scope and who approves live in the profile files; who the people are
lives in the customer files (`src/tta/customers/data/`). The two must agree on the name and on the roles.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from tta.contracts.common import AllergenRelation, AllergenStrictness, ApproverRole, SubstitutionScope, Verdict
from tta.contracts.offer import OfferLine, OfferOption
from tta.contracts.policy import PolicyContext
from tta.policy import PROFILES_DIR, RulePolicyEngine

CUSTOMERS_DIR = Path(PROFILES_DIR).parents[1] / "customers" / "data"
FOUR = ("allergy-ward", "bakery-cafe", "hotel-kitchen", "school-kitchen")
TREE_NUTS, PEANUTS, SESAME = "AN", "AP", "AS"  # GS1 codes (AIMO/docs, allergen code table)


def _customer(customer_id: str) -> dict[str, Any]:
    return yaml.safe_load((CUSTOMERS_DIR / f"{customer_id}.yaml").read_text(encoding="utf-8"))


def test_the_four_customers_each_have_a_profile_and_there_is_no_other(engine: RulePolicyEngine) -> None:
    assert engine.profile_ids() == FOUR


@pytest.mark.parametrize("profile_id", FOUR)
def test_no_shipped_profile_lets_the_agent_order_alone_and_each_says_it_is_illustrative(
    profile_id: str, engine: RulePolicyEngine,
) -> None:
    profile = engine.get_profile(profile_id)

    assert profile.auto_order_enabled is False and profile.illustrative is True
    assert "ILLUSTRATIVE" in (PROFILES_DIR / f"{profile_id}.yaml").read_text(encoding="utf-8")


@pytest.mark.parametrize("profile_id", FOUR)
def test_a_profile_is_named_as_its_customer_file_names_the_customer(profile_id: str, engine: RulePolicyEngine) -> None:
    assert engine.get_profile(profile_id).display_name == _customer(profile_id)["name"]


@pytest.mark.parametrize("profile_id", FOUR)
def test_every_role_a_profile_names_is_a_person_of_the_customer_file_and_someone_can_confirm(
    profile_id: str, engine: RulePolicyEngine,
) -> None:
    roles = engine.get_profile(profile_id).approver_roles

    assert {role.value for role in roles} <= set(_customer(profile_id)["people"])
    assert roles.get(ApproverRole.PURCHASING_MANAGER)  # F-10 names the purchasing manager on every order
    assert all(holders for holders in roles.values())


def test_the_school_keeps_tree_nuts_peanuts_and_sesame_out_for_the_whole_school_under_the_strict_rule(
    engine: RulePolicyEngine,
) -> None:
    school = engine.get_profile("school-kitchen")

    assert school.excluded_allergens == (TREE_NUTS, PEANUTS, SESAME)
    assert school.codes_under(AllergenStrictness.STRICT) == (TREE_NUTS, PEANUTS, SESAME)
    assert school.codes_under(AllergenStrictness.DECLARED_ONLY) == ()
    assert school.substitution_without_approval is SubstitutionScope.LISTED_BY_SUPPLIER
    assert (school.max_order_net_eur, school.max_daily_net_eur, school.min_fill_ratio) == (
        Decimal(250), Decimal(800), Decimal(1)
    )


def test_a_school_product_that_says_nothing_about_nuts_goes_to_the_dietitian(
    engine: RulePolicyEngine, make_line: Callable[..., OfferLine], make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext], make_allergen_check: Callable,
) -> None:
    """Valio Aimo, 14 Nov 2026: when the data leaves a doubt, the safe product wins. No data is not "free from"."""
    school = engine.get_profile("school-kitchen")
    silent = make_allergen_check({
        TREE_NUTS: AllergenRelation.NOT_STATED, PEANUTS: AllergenRelation.FREE_FROM, SESAME: AllergenRelation.FREE_FROM,
    })
    line = make_line("462775", "Arla fat free milkdrink 1 L lactose free", allergen_check=silent)

    decision = engine.evaluate(make_option((line,), net="100.00"), school, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("P-04",)
    assert decision.required_roles == (ApproverRole.DIETITIAN,)


def test_the_bakery_takes_no_substitute_alone_and_names_no_dietitian(engine: RulePolicyEngine) -> None:
    bakery = engine.get_profile("bakery-cafe")

    assert bakery.substitution_without_approval is SubstitutionScope.NONE
    assert bakery.excluded_allergens == () and bakery.allergen_strictness is None
    assert set(bakery.approver_roles) == {ApproverRole.PURCHASING_MANAGER, ApproverRole.FINANCE}
    # The owner holds both roles (the customer file), so one identity signs for either.
    assert bakery.approver_roles[ApproverRole.PURCHASING_MANAGER] == bakery.approver_roles[ApproverRole.FINANCE]
    assert "formula" in (bakery.description or "")
    assert (bakery.max_order_net_eur, bakery.max_daily_net_eur, bakery.min_fill_ratio) == (
        Decimal(300), Decimal(1000), Decimal(1)  # decision B19: sized for a wholesale order
    )


def test_a_substitute_the_supplier_lists_still_goes_to_a_person_at_the_bakery(
    engine: RulePolicyEngine, make_line: Callable[..., OfferLine], make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext], make_substitute: Callable,
) -> None:
    bakery = engine.get_profile("bakery-cafe")
    line = make_line("463975", "Cooking blend 15% 1 L", substitute=make_substitute(listed=True))

    decision = engine.evaluate(make_option((line,), net="40.00"), bakery, make_context())

    assert decision.verdict is Verdict.APPROVAL and "P-05" in decision.rule_ids
    assert "a substitute that Kallio Bakery does not accept without a human" in decision.sentence


def test_the_ward_tolerates_a_tenth_of_drift_and_the_other_three_a_quarter(engine: RulePolicyEngine) -> None:
    drift = {profile_id: engine.get_profile(profile_id).standing_order_drift_ratio for profile_id in FOUR}

    assert drift == {
        "allergy-ward": Decimal("0.1"), "bakery-cafe": Decimal("0.25"), "hotel-kitchen": Decimal("0.25"),
        "school-kitchen": Decimal("0.25"),
    }
