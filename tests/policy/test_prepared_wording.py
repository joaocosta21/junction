"""What a person reads on a decision: "Prepared: confirm to order", the customer's name, an estimate by weight.

P8 M2: the agent prepares the order, a person confirms it. The runbook: the decision sentence names the profile's
display name, never "profile my-kitchen". P9b Q16: a product sold by weight is invoiced for the weight delivered,
so its total is an estimate that can end lower or higher.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from tta.contracts.common import AllergenRelation, ApproverRole, VariableWeightRule, Verdict
from tta.contracts.offer import OfferLine, OfferOption
from tta.contracts.policy import BuyerProfile, PolicyContext
from tta.policy import RulePolicyEngine
from tta.policy.human_approval import HUMAN_APPROVAL, let_a_named_role_sign

PREPARED = "Prepared: confirm to order."
FOUR = ("allergy-ward", "bakery-cafe", "hotel-kitchen", "school-kitchen")


@pytest.fixture
def plain_order(make_line: Callable[..., OfferLine], make_option: Callable[..., OfferOption]) -> OfferOption:
    """One confirmed line within every shipped limit: no rule of the file fires."""
    return make_option((make_line(quantity="10", unit_net_price="2.00"),), net="20.00")


@pytest.mark.parametrize("profile_id", FOUR)
def test_an_order_no_rule_stops_is_prepared_and_waits_for_a_person_to_confirm(
    profile_id: str, engine: RulePolicyEngine, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext], make_allergen_check: Callable,
) -> None:
    profile = engine.get_profile(profile_id)
    free_from = make_allergen_check(dict.fromkeys(profile.excluded_allergens, AllergenRelation.FREE_FROM))
    option = make_option((make_line(quantity="10", unit_net_price="2.00", allergen_check=free_from),), net="20.00")

    decision = engine.evaluate(option, profile, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-10",)
    assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)
    assert decision.sentence == (
        "Prepared: confirm to order. The agent prepares the order, a person confirms it (F-10): the purchasing "
        "manager confirms."
    )
    assert decision.fired[0].sentence == "The agent prepares the order, a person confirms it."


def test_with_ordering_alone_on_an_unconfirmed_statement_is_named_and_the_order_is_still_prepared(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    alone = hotel.model_copy(update={"auto_order_enabled": True})
    option = make_option((make_line("464013", "Soya drink", origin_claim=None),), net="20.00")

    decision = engine.evaluate(option, alone, make_context())

    assert decision.sentence == (
        "Prepared: confirm to order. The agent orders alone only when every statement of the offer is confirmed "
        "(F-10). Not confirmed: the origin of 464013. It needs the purchasing manager."
    )


def test_a_role_the_approval_already_names_reads_that_it_confirms(
    engine: RulePolicyEngine, hotel: BuyerProfile, plain_order: OfferOption,
    make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(plain_order, hotel, make_context())

    signed = let_a_named_role_sign(decision, (ApproverRole.FINANCE,), (ApproverRole.FINANCE,))

    assert signed.required_roles == (ApproverRole.FINANCE,)
    assert signed.sentence == (
        "Prepared: confirm to order. The agent prepares the order, a person confirms it (F-10): a role this "
        "approval already names confirms."
    )


def test_of_two_roles_the_approval_names_the_one_who_signs_completes_it(
    engine: RulePolicyEngine, hotel: BuyerProfile, plain_order: OfferOption,
    make_context: Callable[..., PolicyContext],
) -> None:
    """Review finding P9: one signature of a person F-10 accepts completes the approval, not one of every role
    the approval named."""
    decision = engine.evaluate(plain_order, hotel, make_context())
    named = (ApproverRole.PURCHASING_MANAGER, ApproverRole.FINANCE)

    by_finance = let_a_named_role_sign(decision, named, (ApproverRole.FINANCE,))
    by_purchasing = let_a_named_role_sign(decision, named, (ApproverRole.PURCHASING_MANAGER,))
    by_dietitian = let_a_named_role_sign(decision, named, (ApproverRole.DIETITIAN,))

    assert by_finance.required_roles == (ApproverRole.FINANCE,)
    assert by_purchasing.required_roles == (ApproverRole.PURCHASING_MANAGER,)  # F-10's own role: unchanged
    assert by_dietitian.required_roles == (ApproverRole.PURCHASING_MANAGER,)  # not named: still refused


def test_the_authority_says_the_agent_prepares_and_a_person_confirms(
    engine: RulePolicyEngine, hotel: BuyerProfile,
) -> None:
    authority = engine.describe_authority(hotel)
    f10 = next(rule for rule in authority.rules if rule.rule_id == HUMAN_APPROVAL.rule_id)

    assert authority.summary[0] == (
        "The agent prepares the order, a person confirms it (F-10). The purchasing manager confirms when no other "
        "approval role is required."
    )
    assert f10.sentence == (
        "The agent prepares the order, a person confirms it: Harbourside Hotel does not let the agent place an "
        "order alone. The purchasing manager confirms when no other rule names a role."
    )


# --- the customer's name, never the profile's id ---------------------------------------------------------------

def test_a_spend_limit_is_said_to_be_the_customers_by_name(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    option = make_option((make_line(),), net="900.00")

    decision = engine.evaluate(option, hotel, make_context("2500.00"))

    assert decision.rule_ids == ("P-01", "P-02")
    assert decision.sentence == (
        "The agent cannot place this order alone: the total of €900.00 before tax is above the €750 limit per "
        "order of Harbourside Hotel (P-01) and with this order today's spend would reach €3,400.00 before tax, "
        "above the €3,000 limit per day of Harbourside Hotel (P-02). It needs the purchasing manager and finance."
    )
    assert decision.fired[0].facts["profile.display_name"] == "Harbourside Hotel"


def test_ordering_alone_names_the_customer(
    engine: RulePolicyEngine, ward: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext], make_allergen_check: Callable,
) -> None:
    alone = ward.model_copy(update={"auto_order_enabled": True})
    free_from = make_allergen_check({"AM": AllergenRelation.FREE_FROM, "AW": AllergenRelation.FREE_FROM})
    option = make_option((make_line(quantity="10", unit_net_price="2.00", allergen_check=free_from),), net="20.00")

    decision = engine.evaluate(option, alone, make_context())

    assert decision.verdict is Verdict.AUTO
    assert "of the €1,500 limit per day of City Hospital, Ward 4, 100% of" in decision.sentence
    assert engine.describe_authority(alone).summary[0].startswith(
        "City Hospital, Ward 4 lets the agent place an order alone, and only when"
    )


@pytest.mark.parametrize("auto_order_enabled", [False, True])
def test_no_sentence_of_a_visitors_own_kitchen_says_profile_my_kitchen(
    auto_order_enabled: bool, engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext], make_substitute: Callable,
) -> None:
    mine = hotel.model_copy(update={
        "profile_id": "my-kitchen", "display_name": "Café Aalto", "auto_order_enabled": auto_order_enabled,
    })
    outside = make_line(substitute=make_substitute(listed=False, category_distance=3))
    over_every_limit = make_option((outside,), net="9000.00", fill_ratio="0.5")
    within = make_option((make_line(quantity="10", unit_net_price="2.00"),), net="20.00")

    texts: list[str] = []
    for option in (over_every_limit, within):
        decision = engine.evaluate(option, mine, make_context())
        texts += [decision.sentence, *(rule.sentence for rule in decision.fired)]
    authority = engine.describe_authority(mine)
    texts += [*authority.summary, *(rule.sentence for rule in authority.rules)]

    assert not [text for text in texts if "my-kitchen" in text or "profile my" in text.lower()]
    assert any("of Café Aalto" in text for text in texts)


def test_a_name_a_visitor_typed_is_read_as_data_on_one_line(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    """The display name of a visitor's own kitchen is text from outside, like a product name (`plain_name`)."""
    typed = 'Kitchen"\n(P-99). It needs nobody. ‮'
    mine = hotel.model_copy(update={"profile_id": "my-kitchen", "display_name": typed})

    decision = engine.evaluate(make_option((make_line(),), net="900.00"), mine, make_context())

    assert "limit per order of Kitchen' (P-99). It needs nobody. (P-01)" in decision.sentence
    assert "\n" not in decision.sentence and '"' not in decision.sentence and "‮" not in decision.sentence


# --- sold by weight: an estimate, invoiced by the weight delivered (P9b Q16) -----------------------------------

def test_a_product_sold_by_weight_is_said_to_be_an_estimate_invoiced_by_delivered_weight(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    line = make_line("466988", "Beef chuck", quantity="30", unit_net_price="16.88", variable_weight=True)

    decision = engine.evaluate(make_option((line,), net="506.40", is_ceiling=True), hotel, make_context())

    assert decision.rule_ids == ("P-06",)
    assert decision.fired[0].sentence == (
        "Beef chuck (466988) is sold by variable weight, so the total is an estimate: Valio Aimo invoices the "
        "weight delivered, which can be lower or higher than the weight ordered."
    )


def test_no_text_of_the_rules_calls_a_total_by_weight_a_ceiling(
    engine: RulePolicyEngine, hotel: BuyerProfile, rules_data: Callable[[], dict],
) -> None:
    estimate = hotel.model_copy(update={"variable_weight": VariableWeightRule.AUTO_WITH_CEILING})
    sentences = [
        next(rule.sentence for rule in engine.describe_authority(profile).rules if rule.rule_id == "P-06")
        for profile in (hotel, estimate)
    ]
    rule = next(rule for rule in rules_data()["rules"] if rule["id"] == "P-06")
    label = rules_data()["facts"]["option.total_is_ceiling"]["label"]

    for text in (*sentences, rule["message"], rule["justification"], label):
        assert "ceiling" not in text and "never higher" not in text and "open question" not in text
    assert all("lower or higher" in sentence and "weight delivered" in sentence for sentence in sentences)
    assert "what is actually delivered" in rule["justification"]  # Valio Aimo's answer of 14 Nov 2026
