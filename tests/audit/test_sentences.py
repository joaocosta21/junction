"""One sentence per event, built from a template, for a reader who was not there. Exact wording."""

from __future__ import annotations

import pytest

from tta.audit import AuditTrail
from tta.contracts.audit import AuditContext, AuditEventType
from tta.contracts.common import (
    ApprovalStatus,
    ApproverRole,
    AuditReader,
    DataSource,
    OrderStatus,
    PlacedBy,
    Verdict,
)

ORDER_BY = "Sunday 15 November 2026 at 17:00 (UTC+02:00)"
PARTIAL = "698 pcs of 463380 and 51 pcs of 462775 for €1,980.77 net"
UNCONFIRMED = "1,000 pcs of 464306 for €1,010.00 net"
P01 = "P-01: The order total of €1,980.77 is above the €750.00 limit for one order."
P03 = "P-03: Only 74.9% of the requested quantity is covered; the profile asks for at least 90%."


def test_an_order_placed_by_the_agent_within_its_authority(trail: AuditTrail, samples) -> None:
    order = samples.order(samples.ward_option(), OrderStatus.ORDERED, order_id="ord_2", profile_id="allergy-ward",
                          offer_id="off_2", placed_by=PlacedBy.AGENT, approval_id=None)

    event = trail.record(AuditEventType.ORDER_PLACED_BY_AGENT, samples.agent_ward, AuditContext(order=order))

    assert event.data.sentence == (
        "The agent placed order ord_2 alone, within its authority under the rules of profile allergy-ward: "
        "200 pcs of 464056 for €428.00 net. No rule asked for a human. "
        "The order is recorded in the gateway's order book."
    )
    assert event.data.supplier_sentence == (
        "The agent placed order ord_2 within its authority, without human approval: "
        "200 pcs of 464056 for €428.00 net. The order is recorded in the gateway's order book."
    )
    assert event.data.rule_ids == ()


def test_an_order_sent_to_a_human_names_the_rules(trail: AuditTrail, samples) -> None:
    order = samples.order(samples.partial_option(), OrderStatus.PENDING_APPROVAL)

    event = trail.record(AuditEventType.APPROVAL_REQUESTED, samples.agent_hotel,
                         AuditContext(order=order, approval=samples.approval()))

    assert event.data.sentence == (
        f"The agent could not place order ord_1 alone, because 2 rules ask for a human. {P01} {P03} "
        f"The order ({PARTIAL}) was sent to the purchasing manager, to be decided by {ORDER_BY}."
    )
    assert event.data.supplier_sentence == (
        "The agent could not place order ord_1 alone under the buyer's rules. "
        f"The order ({PARTIAL}) was sent to the buyer's purchasing manager for approval. Rules that applied: "
        "P-01, a rule the buyer set (rule P-01; the amount is not shown): approval by the buyer's purchasing "
        "manager. P-03, a rule the buyer set (rule P-03; the buyer's minimum is not shown): approval by the "
        "buyer's purchasing manager."
    )
    assert event.data.rule_ids == ("P-01", "P-03")


def test_an_order_sent_to_two_roles_for_one_rule(trail: AuditTrail, samples) -> None:
    rule = samples.rule("P-02", "Today's orders would reach €3,400.00, above the €3,000.00 daily limit.",
                        role=ApproverRole.FINANCE)
    option = samples.option("opt_1", (samples.line("464056", "200", "2.14"),), samples.decision(rule), "200")
    approval = samples.approval(roles=(ApproverRole.PURCHASING_MANAGER, ApproverRole.FINANCE))

    event = trail.record(AuditEventType.APPROVAL_REQUESTED, samples.agent_hotel,
                         AuditContext(order=samples.order(option, OrderStatus.PENDING_APPROVAL), approval=approval))

    assert event.data.sentence == (
        "The agent could not place order ord_1 alone, because 1 rule asks for a human. "
        "P-02: Today's orders would reach €3,400.00, above the €3,000.00 daily limit. "
        "The order (200 pcs of 464056 for €428.00 net) was sent to the purchasing manager and finance, "
        f"to be decided by {ORDER_BY}."
    )


def test_an_approval_by_a_named_role_choosing_another_option(trail: AuditTrail, samples) -> None:
    chosen = samples.unconfirmed_option()
    decided = samples.approve(option_id="opt_2", note="The cheaper milk is fine if the stock is there.")
    context = AuditContext(
        order=samples.order(samples.partial_option(), OrderStatus.PENDING_APPROVAL),
        approval=samples.approval(ApprovalStatus.APPROVED, (decided,), option_id="opt_2"),
        approval_decision=decided, option=chosen, decision=chosen.decision,
    )

    event = trail.record(AuditEventType.APPROVAL_DECIDED, samples.maija, context)

    assert event.data.sentence == (
        "Maija Virtanen (purchasing manager) approved order ord_1 and chose another option of the same offer: "
        f"opt_2 ({UNCONFIRMED}) instead of opt_1. This approval accepts rules F-01 and P-01. "
        'Note: "The cheaper milk is fine if the stock is there."'
    )
    assert event.data.supplier_sentence == (
        "The buyer's purchasing manager approved order ord_1 and chose another option of the same offer: "
        f"opt_2 ({UNCONFIRMED}) instead of opt_1. This approval accepts rules F-01 and P-01."
    )
    assert event.data.rule_ids == ("F-01", "P-01")


def test_an_approval_of_the_option_first_asked_for(trail: AuditTrail, samples) -> None:
    decided = samples.approve()
    roles = (ApproverRole.PURCHASING_MANAGER, ApproverRole.FINANCE)
    context = AuditContext(
        order=samples.order(samples.partial_option(), OrderStatus.PENDING_APPROVAL),
        approval=samples.approval(ApprovalStatus.PENDING, (decided,), roles=roles), approval_decision=decided,
    )

    event = trail.record(AuditEventType.APPROVAL_DECIDED, samples.maija, context)

    assert event.data.sentence == (
        "Maija Virtanen (purchasing manager) approved order ord_1. This approval accepts rules P-01 and P-03. "
        "The order still needs approval by finance."
    )
    assert event.data.supplier_sentence == (
        "The buyer's purchasing manager approved order ord_1. This approval accepts rules P-01 and P-03. "
        "The order still needs approval by the buyer's finance."
    )


def test_a_rejection(trail: AuditTrail, samples) -> None:
    decided = samples.reject(note="Too expensive\nthis week.")
    context = AuditContext(
        order=samples.order(samples.partial_option(), OrderStatus.REJECTED),
        approval=samples.approval(ApprovalStatus.REJECTED, (decided,)), approval_decision=decided,
    )

    decision_event = trail.record(AuditEventType.APPROVAL_DECIDED, samples.maija, context)
    order_event = trail.record(AuditEventType.ORDER_REJECTED, samples.gateway, context)

    assert decision_event.data.sentence == (
        'Maija Virtanen (purchasing manager) rejected order ord_1. Note: "Too expensive this week."'
    )
    assert order_event.data.sentence == (
        "Order ord_1 was rejected by Maija Virtanen (purchasing manager). Nothing was ordered. "
        'Note: "Too expensive this week."'
    )
    assert decision_event.data.supplier_sentence == "The buyer's purchasing manager rejected order ord_1."
    assert order_event.data.supplier_sentence == (
        "Order ord_1 was rejected by the buyer's purchasing manager. Nothing was ordered."
    )


def test_an_expiry(trail: AuditTrail, samples) -> None:
    context = AuditContext(order=samples.order(samples.partial_option(), OrderStatus.EXPIRED),
                           approval=samples.approval(ApprovalStatus.EXPIRED))

    event = trail.record(AuditEventType.ORDER_EXPIRED, samples.gateway, context)

    assert event.data.sentence == (
        "Order ord_1 expired without a decision: the approval by the purchasing manager was still missing on "
        f"{ORDER_BY}, when the offer stopped being valid. Nothing was ordered."
    )
    assert event.data.supplier_sentence == (
        "Order ord_1 expired while it waited for approval by the buyer's purchasing manager. Nothing was ordered."
    )


def test_an_order_confirmed_after_approval(hotel_flow: AuditTrail) -> None:
    event = hotel_flow.view(AuditReader.BUYER, order_id="ord_1").events[-1]

    assert event.sentence == (
        f"Order ord_1 is ordered, with approval by Maija Virtanen (purchasing manager): {UNCONFIRMED}. "
        "Price and availability were checked again and had not changed. "
        "The order is recorded in the gateway's order book."
    )


def test_the_request_and_the_offer_are_described_with_their_numbers(hotel_flow: AuditTrail) -> None:
    sentences = [event.sentence for event in hotel_flow.view(AuditReader.BUYER, order_id="ord_1").events]

    assert sentences[:5] == [
        'The agent sent a request for profile hotel-kitchen: "1,000 litres of lactose-free milk by Monday".',
        "The request was read as: 1,000 litres of product type lactose_free_milk with claim FREE_FROM_LACTOSE, "
        "needed by Monday 16 November 2026.",
        "The gateway looked up price and availability of 35 products in a recorded copy of Valio Aimo's data.",
        "The gateway built offer off_1 from a recorded copy of Valio Aimo's data: 2 options from "
        f"35 candidates, 2 products excluded with a reason. Option 1 (best confirmed): {PARTIAL}, covering 74.9% "
        f"of the request. Option 2 (alternative, quantity not confirmed): {UNCONFIRMED}, covering the full quantity.",
        "The rules of Hotel kitchen were checked for option opt_1. The agent cannot place this order "
        "alone: the total of €1,980.77 before tax is above the €750 limit per order (P-01) and only 74.9% of the "
        "requested quantity is covered (P-03). It needs the purchasing manager.",
    ]


def test_the_ward_request_names_its_allergen_exclusions_for_the_buyer_only(ward_flow: AuditTrail) -> None:
    buyer = ward_flow.view(AuditReader.BUYER, offer_id="off_2").events
    supplier = ward_flow.view(AuditReader.SUPPLIER, offer_id="off_2").events

    assert buyer[0].sentence == (
        "The request was read as: 200 litres of product type milk_substitute, excluding allergens AM and AW "
        "(STRICT), needed by Monday 16 November 2026, confirmed data only."
    )
    assert supplier[0].sentence == (
        "The request was read as: 200 litres of product type milk_substitute, needed by Monday 16 November 2026, "
        "confirmed data only."
    )
    assert buyer[2].sentence == (
        "The rules of profile allergy-ward were checked for option opt_1. The agent may place this order alone: "
        "the total of €428.00 before tax is within the €500 limit per order and no rule asks for a human."
    )
    assert supplier[2].sentence == (
        "The buyer's rules were checked for option opt_1: the agent may place this order within its authority. "
        "No rule applied."
    )


def test_a_blocked_order_says_why_and_that_nothing_was_ordered(trail: AuditTrail, samples) -> None:
    rule = samples.rule("F-05", "471881 adds gluten (AW), which 473609 does not declare.", verdict=Verdict.BLOCK,
                        role=None, product_id="471881")
    option = samples.option("opt_3", (samples.line("471881", "10", "1.95"),),
                            samples.decision(rule, profile_id="allergy-ward"), "10")

    event = trail.record(AuditEventType.ORDER_BLOCKED, samples.agent_ward,
                         AuditContext(offer_id="off_2", option=option))

    assert event.data.sentence == (
        "The rules of profile allergy-ward blocked the order of option opt_3 of offer off_2: it cannot be placed, "
        "even with approval. F-05: 471881 adds gluten (AW), which 473609 does not declare. Nothing was ordered."
    )
    assert event.data.supplier_sentence == (
        "The buyer's rules blocked the order of option opt_3 of offer off_2. Nothing was ordered. "
        "Rule that applied: F-05, a fixed rule (rule F-05), on product 471881: the order cannot be placed."
    )
    assert event.subject == "offer/off_2"


def test_an_order_not_placed_because_the_price_changed(trail: AuditTrail, samples) -> None:
    context = AuditContext(offer_id="off_1", option=samples.partial_option(),
                           revalidation=samples.revalidation(changed=True))

    event = trail.record(AuditEventType.ORDER_NOT_PLACED, samples.agent_hotel, context)

    expected = (
        "The order of option opt_1 of offer off_1 was not placed: price or availability changed since the offer "
        "was made. The price of 463380 changed from €2.65 to €2.80. "
        "The buyer's agent can ask for a fresh offer."
    )
    assert event.data.sentence == expected
    assert event.data.supplier_sentence == expected


def test_an_order_not_placed_because_the_offer_expired(trail: AuditTrail, samples) -> None:
    context = AuditContext(offer_id="off_1", option=samples.partial_option(),
                           revalidation=samples.revalidation(expired=True))

    event = trail.record(AuditEventType.ORDER_NOT_PLACED, samples.agent_hotel, context)

    assert event.data.sentence == (
        "The order of option opt_1 of offer off_1 was not placed: the offer is no longer valid, because its "
        '"order by" time, a price validity or a cut-off has passed. The buyer\'s agent can ask for a fresh offer.'
    )


def test_an_agent_on_an_approval_route_is_refused_and_recorded(trail: AuditTrail, samples) -> None:
    event = trail.record(AuditEventType.AUTHORISATION_REFUSED, samples.agent_hotel,
                         AuditContext(approval=samples.approval()))

    expected = "The agent tried to decide approval apr_1 and was refused: an agent cannot approve an order (F-06)."
    assert event.data.sentence == expected
    assert event.data.supplier_sentence == expected
    assert event.data.rule_ids == ("F-06",)


def test_a_human_who_may_not_decide_is_refused_with_the_reason(trail: AuditTrail, samples) -> None:
    context = AuditContext(approval=samples.approval(), facts={"reason": "The approval needs finance."})

    event = trail.record(AuditEventType.AUTHORISATION_REFUSED, samples.maija, context)

    assert event.data.sentence == (
        "Maija Virtanen (purchasing manager) was refused on approval apr_1: this caller may not decide it. "
        "The approval needs finance."
    )
    assert event.data.supplier_sentence == (
        "The buyer's purchasing manager was refused on approval apr_1: this caller may not decide it."
    )
    assert event.data.rule_ids == ()


def test_evidence_is_described_as_outside_valio_data(trail: AuditTrail, samples) -> None:
    event = trail.record(AuditEventType.EVIDENCE_ATTACHED, samples.gateway,
                         AuditContext(approval=samples.approval(), evidence=samples.evidence()))

    assert event.data.sentence == (
        "Evidence from outside Valio Aimo's data was attached to approval apr_1 for product 473609: "
        "The manufacturer's page lists oats and no milk. It changes no status and no verdict."
    )
    assert event.data.supplier_sentence == (
        "Evidence from outside Valio Aimo's data was attached to an approval for product 473609. "
        "It changes no status and no verdict."
    )


def test_an_offer_with_no_option_says_so(trail: AuditTrail, samples) -> None:
    offer = samples.ward_offer().model_copy(update={"options": ()})

    event = trail.record(AuditEventType.OFFER_CREATED, samples.gateway, AuditContext(offer=offer))

    assert event.data.sentence == (
        "The gateway built offer off_2 from a recorded copy of Valio Aimo's data: no option fits the "
        "request; 12 candidates, 2 products excluded with a reason. Every product declaring AM or AW was left out."
    )
    assert event.data.supplier_sentence == (
        "The gateway built offer off_2 from a recorded copy of Valio Aimo's data: no option fits the "
        "request; 12 candidates. 2 products were considered and left out: 2 declaring an allergen the buyer "
        "excludes (which allergen and which products are not shown)."
    )


@pytest.mark.parametrize("event_type", list(AuditEventType))
def test_every_event_type_has_a_sentence_for_both_readers_even_with_nothing_known(
    trail: AuditTrail, samples, event_type: AuditEventType
) -> None:
    event = trail.record(event_type, samples.gateway, AuditContext())

    for sentence in (event.data.sentence, event.data.supplier_sentence):
        assert sentence[0].isupper() and sentence.endswith(".")
        assert "None" not in sentence


def test_a_typed_request_sent_without_pasted_text_is_described_from_its_fields(trail: AuditTrail, samples) -> None:
    context = AuditContext(profile_id="allergy-ward", request=samples.ward_request())

    event = trail.record(AuditEventType.REQUEST_RECEIVED, samples.agent_ward, context)

    assert event.data.sentence == (
        "The agent sent a request for profile allergy-ward: 200 litres of product type milk_substitute, "
        "excluding allergens AM and AW (STRICT), needed by Monday 16 November 2026, confirmed data only."
    )
    assert event.data.supplier_sentence == "The buyer's agent sent a purchase request."


def test_a_lookup_takes_its_figures_from_the_offer_when_one_is_given(trail: AuditTrail, samples) -> None:
    live = samples.hotel_offer().model_copy(update={"source": DataSource.LIVE})

    event = trail.record(AuditEventType.LOOKUP_PERFORMED, samples.gateway, AuditContext(offer=live))

    expected = "The gateway looked up price and availability of 35 products in Valio Aimo's live data."
    assert event.data.sentence == expected
    assert event.data.supplier_sentence == expected


def test_a_blocking_verdict_is_explained_to_the_buyer(trail: AuditTrail, samples) -> None:
    rule = samples.rule("F-02", "464306 declares milk (AM), which this profile excludes.", verdict=Verdict.BLOCK,
                        role=None, product_id="464306")
    blocked = "This order cannot be placed, even with approval: 464306 declares an allergen this buyer excludes (F-02)."
    option = samples.option("opt_1", (samples.line("464306", "200", "1.01"),),
                            samples.decision(rule, profile_id="allergy-ward", sentence=blocked), "200")

    event = trail.record(AuditEventType.POLICY_EVALUATED, samples.gateway,
                         AuditContext(offer_id="off_2", option=option))

    assert event.data.sentence == f"The rules of profile allergy-ward were checked for option opt_1. {blocked}"
    assert event.data.rule_ids == ("F-02",)
    assert event.data.supplier_sentence == (
        "The buyer's rules were checked for option opt_1: this order cannot be placed. "
        "Rule that applied: F-02, a fixed rule (rule F-02; which allergen and which product are not shown): "
        "the order cannot be placed. The strictest outcome among the rules that applied decides."
    )
    assert "464306" not in event.data.supplier_sentence and "AM" not in event.data.supplier_sentence


def test_an_order_confirmed_without_an_approval_says_the_agent_placed_it(trail: AuditTrail, samples) -> None:
    order = samples.order(samples.ward_option(), OrderStatus.ORDERED, order_id="ord_2", profile_id="allergy-ward",
                          offer_id="off_2", placed_by=PlacedBy.AGENT, approval_id=None)

    event = trail.record(AuditEventType.ORDER_CONFIRMED, samples.gateway, AuditContext(order=order))

    expected = (
        "Order ord_2 is ordered, placed by the agent within its authority: 200 pcs of 464056 for €428.00 net. "
        "The order is recorded in the gateway's order book."
    )
    assert event.data.sentence == expected
    assert event.data.supplier_sentence == expected


def test_a_total_by_weight_is_an_estimate_and_missing_deposits_are_said(trail: AuditTrail, samples) -> None:
    option = samples.ward_option()
    totals = option.totals.model_copy(update={"is_ceiling": True, "excludes_deposits": True})
    order = samples.order(option.model_copy(update={"totals": totals}), OrderStatus.ORDERED, placed_by=PlacedBy.AGENT)

    event = trail.record(AuditEventType.ORDER_PLACED_BY_AGENT, samples.agent_hotel, AuditContext(order=order))

    for sentence in (event.data.sentence, event.data.supplier_sentence):
        assert (
            "200 pcs of 464056 for about €428.00 net (an estimate: sold by weight, Valio Aimo invoices the weight "
            "delivered), deposits not included."
        ) in sentence
        assert [word for word in ("at most", "ceiling", "never higher", "maximum") if word in sentence] == []


def test_an_approval_of_an_order_no_rule_asked_about_names_no_rule(trail: AuditTrail, samples) -> None:
    decided = samples.approve()
    context = AuditContext(order=samples.order(samples.ward_option(), OrderStatus.PENDING_APPROVAL),
                           approval=samples.approval(ApprovalStatus.APPROVED, (decided,)), approval_decision=decided)

    event = trail.record(AuditEventType.APPROVAL_DECIDED, samples.maija, context)

    assert event.data.sentence == "Maija Virtanen (purchasing manager) approved order ord_1."


def test_a_rule_that_fires_on_two_lines_is_counted_once_and_explained_twice(trail: AuditTrail, samples) -> None:
    decision = samples.decision(
        samples.rule("F-01", "The quantity of 464306 is not confirmed by Valio Aimo.", product_id="464306"),
        samples.rule("F-01", "The quantity of 473609 is not confirmed by Valio Aimo.", product_id="473609"),
    )
    option = samples.option("opt_1", (samples.line("464306", "100", "1.01"), samples.line("473609", "100", "1.95")),
                            decision, "200")
    decided = samples.approve()
    order = samples.order(option, OrderStatus.PENDING_APPROVAL)

    requested = trail.record(AuditEventType.APPROVAL_REQUESTED, samples.agent_hotel,
                             AuditContext(order=order, approval=samples.approval()))
    approved = trail.record(AuditEventType.APPROVAL_DECIDED, samples.maija,
                            AuditContext(order=order, approval=samples.approval(ApprovalStatus.APPROVED, (decided,)),
                                         approval_decision=decided))

    assert requested.data.rule_ids == ("F-01",)
    assert requested.data.sentence.startswith(
        "The agent could not place order ord_1 alone, because 1 rule asks for a human. "
        "F-01: The quantity of 464306 is not confirmed by Valio Aimo. "
        "F-01: The quantity of 473609 is not confirmed by Valio Aimo. The order ("
    )
    assert requested.data.supplier_sentence.endswith(
        "Rule that applied: F-01, a fixed rule (rule F-01), on products 464306 and 473609: "
        "approval by the buyer's purchasing manager."
    )
    assert approved.data.sentence == (
        "Maija Virtanen (purchasing manager) approved order ord_1. This approval accepts rule F-01."
    )
    assert len(requested.data.facts["decision"]["fired"]) == 2
