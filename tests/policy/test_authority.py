"""`describe_authority`: what the calling agent may decide alone, in plain language (GET /v1/authority)."""

from __future__ import annotations

from tta.contracts.common import ApproverRole, SubstitutionScope, VariableWeightRule, Verdict
from tta.contracts.policy import Authority, BuyerProfile
from tta.policy import RulePolicyEngine


def _sentence(authority: Authority, rule_id: str) -> str:
    return next(rule.sentence for rule in authority.rules if rule.rule_id == rule_id)


def test_authority_lists_every_rule_with_this_profiles_values(engine: RulePolicyEngine, hotel: BuyerProfile) -> None:
    authority = engine.describe_authority(hotel)

    assert authority.profile == hotel
    assert authority.policy_hash == engine.policy_hash(hotel)
    assert [rule.rule_id for rule in authority.rules] == [
        "F-01", "F-02", "F-03", "F-04", "F-05", "F-07", "F-08", "F-09", "F-11", "F-12",
        "F-10", "P-01", "P-02", "P-03", "P-04", "P-05", "P-06", "P-07", "P-08", "P-09",
    ]
    # F-10 is driven by the buyer's setting, so it stands with the profile rules and is not fixed.
    assert [rule.fixed for rule in authority.rules] == [True] * 10 + [False] * 10
    assert _sentence(authority, "P-01") == "An order above €750 before tax goes to the purchasing manager."
    # No customer has a finance signer of its own: the sentence names who really decides (decision B54).
    assert _sentence(authority, "P-02") == (
        "When the day's orders, this one included, pass €3,000 before tax, the order goes to the purchasing manager."
    )
    assert _sentence(authority, "P-03") == (
        "An option that covers less than 90% of the requested quantity goes to the purchasing manager."
    )


def test_authority_rules_carry_their_verdict_and_role(engine: RulePolicyEngine, hotel: BuyerProfile) -> None:
    rules = {rule.rule_id: rule for rule in engine.describe_authority(hotel).rules}

    assert rules["F-02"].verdict is Verdict.BLOCK and rules["F-02"].approver_role is None
    assert rules["F-01"].verdict is Verdict.APPROVAL
    assert rules["F-01"].approver_role is ApproverRole.PURCHASING_MANAGER
    assert rules["P-02"].approver_role is ApproverRole.FINANCE
    assert rules["P-04"].approver_role is ApproverRole.DIETITIAN


def test_authority_summary_says_what_the_agent_may_do_alone(engine: RulePolicyEngine, hotel: BuyerProfile) -> None:
    summary = engine.describe_authority(hotel).summary

    assert "The agent prepares the order, a person confirms it (F-10)" in summary[0]
    assert all(value in summary[1] for value in ("750", "3,000", "90%"))
    assert any("quantity is not confirmed" in line for line in summary)
    assert any("price is not confirmed" in line and "needed-by date" in line for line in summary)
    assert any("even with approval" in line for line in summary)
    assert summary[-1] == "An agent can never approve an order, its own included: approval routes refuse agent tokens."


def test_authority_says_that_the_limit_values_are_illustrative(engine: RulePolicyEngine, ward: BuyerProfile) -> None:
    note = engine.describe_authority(ward).note

    assert "illustrative" in note and "Valio Aimo mock has no customer limits" in note


def test_authority_follows_the_profile_settings(
    engine: RulePolicyEngine, hotel: BuyerProfile, ward: BuyerProfile
) -> None:
    ward_authority = engine.describe_authority(ward)
    hotel_authority = engine.describe_authority(hotel)
    alone = engine.describe_authority(hotel.model_copy(update={"auto_order_enabled": True}))
    ceiling = engine.describe_authority(
        hotel.model_copy(update={"variable_weight": VariableWeightRule.AUTO_WITH_CEILING})
    )
    listed = engine.describe_authority(
        hotel.model_copy(update={"substitution_without_approval": SubstitutionScope.LISTED_BY_SUPPLIER})
    )

    # Allergens in words, the customer by its name: never a code, never "this profile".
    assert _sentence(ward_authority, "P-04") == (
        "City Hospital, Ward 4 excludes milk and cereals containing gluten, and each must be confirmed absent: a "
        "product that may contain one, leaves it undeclared or says nothing about it goes to the dietitian."
    )
    assert _sentence(ward_authority, "F-02") == (
        "City Hospital, Ward 4 excludes milk and cereals containing gluten. A product that contains one of them "
        "can never be ordered, even with approval."
    )
    assert "excludes no allergen" in _sentence(hotel_authority, "P-04")
    assert _sentence(ward_authority, "P-05") == "Every substitute goes to the purchasing manager."
    assert "same product category" in _sentence(hotel_authority, "P-05")
    assert "does not list" in _sentence(listed, "P-05") and "category" not in _sentence(listed, "P-05")
    assert hotel.auto_order_enabled is False
    assert "does not let the agent place an order alone" in _sentence(hotel_authority, "F-10")
    assert "every statement of the offer is confirmed: price, quantity, delivery date" in _sentence(alone, "F-10")
    assert alone.summary[0].startswith("Harbourside Hotel lets the agent place an order alone, and only when")
    assert alone.summary[1] == (
        "Alone, at most: €750 before tax per order and €3,000 before tax per day, this order included, with at "
        "least 90% of the requested quantity covered."
    )
    assert alone.policy_hash != hotel_authority.policy_hash  # the setting is part of what is hashed
    # Valio Aimo, 14 Nov 2026: a product sold by weight is invoiced for the weight delivered. Never a ceiling.
    assert "needs no approval of its own when the offer marks its total as an estimate" in _sentence(ceiling, "P-06")
    assert "goes to the purchasing manager: its total is an estimate" in _sentence(hotel_authority, "P-06")
    assert "ceiling" not in _sentence(ceiling, "P-06") + _sentence(hotel_authority, "P-06")


def test_authority_serialises_to_json(engine: RulePolicyEngine, ward: BuyerProfile) -> None:
    authority = engine.describe_authority(ward)

    assert Authority.model_validate_json(authority.model_dump_json()) == authority


def test_authority_lists_f07_once_with_what_it_says_about_a_line_and_about_the_option(
    engine: RulePolicyEngine, hotel: BuyerProfile
) -> None:
    f07 = [rule for rule in engine.describe_authority(hotel).rules if rule.rule_id == "F-07"]

    assert len(f07) == 1
    assert f07[0].fixed and f07[0].verdict is Verdict.APPROVAL
    assert f07[0].approver_role is ApproverRole.PURCHASING_MANAGER
    assert f07[0].sentence == (
        "A product whose price Valio Aimo does not confirm, or whose delivery date is ruled out, always goes to "
        "the purchasing manager. When the request gives a needed-by date, an option that does not verifiably "
        "meet it always goes to the purchasing manager."
    )
