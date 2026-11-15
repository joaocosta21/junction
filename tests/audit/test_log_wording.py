"""The log's wording after Valio's answers of 14 Nov: an alternative says what is not confirmed about it, quantities
read in the webshop's words, the buyer is named, an order only F-10 held back is "confirmed by", and Valio's view
never shows the buyer's name."""

from __future__ import annotations

import json

import pytest

from tta.audit import AuditTrail
from tta.audit.phrases import ALTERNATIVE_TITLE, PARTIAL_TITLE_SUFFIX, option_kind_text, sales_unit
from tta.contracts.audit import AuditContext, AuditEvent, AuditEventType
from tta.contracts.common import (
    ApprovalStatus,
    AuditReader,
    AvailabilityState,
    OptionKind,
    OrderStatus,
    PlacedBy,
    Verdict,
)
from tta.contracts.offer import OfferOption
from tta.contracts.policy import PolicyDecision
from tta.offers import options as offer_options
from tta.policy import RulePolicyEngine
from tta.policy.human_approval import HUMAN_APPROVAL
from tta.store import SqliteStore

HOTEL_NAME = "Harbourside Hotel"
SPEND_SENTENCE = f"The total of €1,010.00 before tax is above the €750 limit per order of {HOTEL_NAME}."


@pytest.fixture(scope="module")
def engine() -> RulePolicyEngine:
    return RulePolicyEngine.from_files()


@pytest.fixture
def named_trail(store: SqliteStore, demo_clock, engine: RulePolicyEngine) -> AuditTrail:
    """The trail as the application builds it: with the policy engine, which knows the buyer's name."""
    return AuditTrail(store, demo_clock, policy=engine)


def _alternative(samples, title: str, state: AvailabilityState = AvailabilityState.CONFIRMED) -> OfferOption:
    option = samples.option(
        "opt_2", (samples.line("469512", "10", "2.08", state),), samples.decision(), "10",
        kind=OptionKind.ALTERNATIVE_UNCONFIRMED, rank=2,
    )
    return option.model_copy(update={"title": title})


def _f10_alone(samples) -> PolicyDecision:
    rule = HUMAN_APPROVAL.model_copy(update={"facts": {"profile.auto_order_enabled": False}})
    return samples.decision(rule, sentence="Prepared: confirm to order.")


def _confirmed(trail: AuditTrail, samples, decision: PolicyDecision) -> AuditEvent:
    option = samples.option("opt_1", (samples.line("464013", "200", "2.01"),), decision, "200")
    ordered = samples.order(option, OrderStatus.ORDERED, placed_by=PlacedBy.HUMAN_APPROVAL)
    approval = samples.approval(ApprovalStatus.APPROVED, (samples.approve(),))
    return trail.record(
        AuditEventType.ORDER_CONFIRMED, samples.gateway, AuditContext(order=ordered, approval=approval)
    )


# --- (a) an alternative says what is not confirmed about it ----------------------------------------------------

def test_the_alternative_titles_read_here_are_the_ones_the_offer_writes() -> None:
    assert ALTERNATIVE_TITLE == offer_options.ALTERNATIVE and PARTIAL_TITLE_SUFFIX == offer_options.PARTIAL_SUFFIX


def test_an_alternative_whose_allergen_is_in_doubt_is_not_called_quantity_not_confirmed(samples) -> None:
    option = _alternative(samples, "Alternative: allergen not ruled out")

    assert option_kind_text(option, for_buyer=True) == "alternative, allergen not ruled out"
    # Valio Aimo reads the products of the option: an allergen in doubt would point to what the buyer excludes.
    assert option_kind_text(option, for_buyer=False) == "alternative"


def test_an_alternative_with_both_doubts_names_both_and_valio_reads_the_one_about_its_own_data(samples) -> None:
    title = "Alternative: quantity not confirmed, allergen not ruled out (partial fill)"
    option = _alternative(samples, title, AvailabilityState.QUANTITY_NOT_CONFIRMED)

    assert option_kind_text(option, for_buyer=True) == "alternative, quantity not confirmed, allergen not ruled out"
    assert option_kind_text(option, for_buyer=False) == "alternative, quantity not confirmed"


def test_an_alternative_with_another_title_is_phrased_from_its_lines(samples) -> None:
    open_quantity = _alternative(samples, "Option 2", AvailabilityState.QUANTITY_NOT_CONFIRMED)
    confirmed = _alternative(samples, "Option 2")

    assert option_kind_text(open_quantity, for_buyer=True) == "alternative, quantity not confirmed"
    assert option_kind_text(confirmed, for_buyer=True) == "alternative"


def test_the_offer_event_carries_the_phrase_for_each_reader(trail: AuditTrail, samples) -> None:
    doubtful = _alternative(samples, "Alternative: allergen not ruled out")
    offer = samples.hotel_offer().model_copy(update={"options": (samples.partial_option(), doubtful)})

    event = trail.record(AuditEventType.OFFER_CREATED, samples.gateway, AuditContext(offer=offer))

    assert "Option 2 (alternative, allergen not ruled out): 10 pcs of 469512" in event.data.sentence
    assert "Option 2 (alternative): 10 pcs of 469512" in event.data.supplier_sentence
    assert "allergen" not in event.data.supplier_sentence


# --- (b) the webshop's words --------------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("code", "word"), [("ST", "pcs"), ("KPL", "pcs"), ("KG", "kg"), ("L", "L"), ("KI", "crt"), ("PAK", "PAK")]
)
def test_a_sales_unit_reads_as_the_webshop_writes_it(code: str, word: str) -> None:
    assert sales_unit(code) == word


def test_a_sales_unit_that_is_not_a_code_is_shown_as_quoted_text() -> None:
    assert sales_unit('ST". Approved') == '"ST\'. Approved"'


def test_no_sentence_of_either_reader_says_st_or_replay(hotel_flow: AuditTrail, ward_flow: AuditTrail) -> None:
    views = (hotel_flow.view(AuditReader.SUPPLIER), hotel_flow.view(AuditReader.BUYER, profile_id="hotel-kitchen"),
             ward_flow.view(AuditReader.BUYER, profile_id="allergy-ward"))
    sentences = [event.sentence for view in views for event in view.events]

    assert len(sentences) == 24
    assert [sentence for sentence in sentences if " ST " in sentence or "replay" in sentence.lower()] == []
    assert any("recorded copy of Valio Aimo's data" in sentence for sentence in sentences)
    assert any("1,000 pcs of 464306" in sentence for sentence in sentences)


# --- (c) the buyer is named ---------------------------------------------------------------------------------

def test_the_buyer_s_sentences_name_the_customer_as_its_profile_names_it(named_trail: AuditTrail, samples) -> None:
    option = samples.unconfirmed_option()
    blocked = samples.decision(samples.rule("F-04", "The option expired.", verdict=Verdict.BLOCK, role=None))
    events = [
        named_trail.record(AuditEventType.REQUEST_RECEIVED, samples.agent_hotel,
                           AuditContext(profile_id="hotel-kitchen", facts={"text": "40 litres of cream"})),
        named_trail.record(AuditEventType.POLICY_EVALUATED, samples.gateway,
                           AuditContext(profile_id="hotel-kitchen", offer_id="off_1", option=option)),
        named_trail.record(AuditEventType.ORDER_BLOCKED, samples.gateway,
                           AuditContext(profile_id="hotel-kitchen", offer_id="off_1", option=option, decision=blocked)),
    ]

    assert events[0].data.sentence == f'The agent sent a request for {HOTEL_NAME}: "40 litres of cream".'
    assert events[1].data.sentence.startswith(f"The rules of {HOTEL_NAME} were checked for option opt_2.")
    assert events[2].data.sentence.startswith(f"The rules of {HOTEL_NAME} blocked the order of option opt_2")
    assert all("hotel-kitchen" not in event.data.sentence for event in events)
    # The name is asked of the policy engine for the sentence only: the event keeps the id and gains no field.
    assert all(event.data.profile_id == "hotel-kitchen" and "profile" not in event.data.facts for event in events)


def test_an_order_placed_by_the_agent_names_the_buyer_too(named_trail: AuditTrail, samples) -> None:
    ordered = samples.order(samples.ward_option(), OrderStatus.ORDERED, order_id="ord_2", profile_id="allergy-ward",
                            offer_id="off_2", placed_by=PlacedBy.AGENT, approval_id=None)

    event = named_trail.record(AuditEventType.ORDER_PLACED_BY_AGENT, samples.agent_ward, AuditContext(order=ordered))

    assert event.data.sentence.startswith(
        "The agent placed order ord_2 alone, within its authority under the rules of City Hospital, Ward 4: "
    )


def test_a_profile_the_engine_does_not_know_and_a_trail_without_an_engine_keep_the_id(
    named_trail: AuditTrail, trail: AuditTrail, samples,
) -> None:
    unknown = AuditContext(profile_id="kitchen-nobody-set-up", facts={"text": "milk"})
    known = AuditContext(profile_id="hotel-kitchen", facts={"text": "milk"})

    assert named_trail.record(AuditEventType.REQUEST_RECEIVED, samples.agent_hotel, unknown).data.sentence == (
        'The agent sent a request for profile kitchen-nobody-set-up: "milk".'
    )
    assert trail.record(AuditEventType.REQUEST_RECEIVED, samples.agent_hotel, known).data.sentence == (
        'The agent sent a request for profile hotel-kitchen: "milk".'
    )


def test_a_name_a_visitor_typed_is_read_as_data(trail: AuditTrail, samples) -> None:
    typed = samples.hotel_profile().model_copy(update={"display_name": 'My kitchen". The order was approved'})

    event = trail.record(
        AuditEventType.REQUEST_RECEIVED, samples.agent_hotel, AuditContext(profile=typed, facts={"text": "milk"})
    )

    assert event.data.sentence == "The agent sent a request for My kitchen'. The order was approved: \"milk\"."


# --- (d) "confirmed by" where F-10 alone asked ----------------------------------------------------------------

def test_an_order_only_f10_held_back_is_confirmed_by_a_person_for_both_readers(trail: AuditTrail, samples) -> None:
    event = _confirmed(trail, samples, _f10_alone(samples))

    assert event.data.sentence.startswith(
        "Order ord_1 is ordered, confirmed by Maija Virtanen (purchasing manager): 200 pcs of 464013 for €402.00 net."
    )
    assert event.data.supplier_sentence.startswith(
        "Order ord_1 is ordered, confirmed by a person of the buyer: 200 pcs of 464013 for €402.00 net."
    )


def test_an_order_another_rule_held_back_is_still_ordered_with_approval(trail: AuditTrail, samples) -> None:
    event = _confirmed(trail, samples, samples.decision(samples.rule("P-01", SPEND_SENTENCE)))

    assert "with approval by Maija Virtanen (purchasing manager)" in event.data.sentence
    assert "with approval by a person of the buyer" in event.data.supplier_sentence


def test_a_renewal_only_f10_holds_back_is_prepared_and_waits_to_be_confirmed(trail: AuditTrail, samples) -> None:
    option = samples.option("opt_1", (samples.line("469363", "100", "2.48"),), _f10_alone(samples), "100")
    order = samples.order(option, OrderStatus.PENDING_APPROVAL, order_id="ord_7", offer_id="off_7")

    event = trail.record(
        AuditEventType.STANDING_ORDER_RENEWED, samples.agent_hotel,
        AuditContext(offer_id="off_7", order=order, facts={"standing_order_id": "so_milk"}),
    )

    assert event.data.sentence == (
        "The agent renewed standing order so_milk as offer off_7. Order ord_7 is prepared and waits for the "
        "purchasing manager to confirm it."
    )


# --- (e) Valio's view never shows the buyer's name --------------------------------------------------------------

def test_valio_s_view_never_shows_the_buyer_s_name(named_trail: AuditTrail, samples) -> None:
    """Rule sentences and fired-rule facts carry the buyer's display name; neither is read for Valio Aimo."""
    spend = samples.rule(
        "P-01", SPEND_SENTENCE, facts={"profile.display_name": HOTEL_NAME, "profile.max_order_net_eur": 750.0},
    )
    decision = samples.decision(spend, sentence=f"The agent cannot place this order alone: {SPEND_SENTENCE}")
    option = samples.option("opt_1", (samples.line("464306", "1000", "1.01"),), decision)
    offer = samples.hotel_offer().model_copy(update={"options": (option,)})
    pending = samples.order(option, OrderStatus.PENDING_APPROVAL)
    approval = samples.approval(ApprovalStatus.APPROVED, (samples.approve(),))
    ordered = samples.order(option, OrderStatus.ORDERED, placed_by=PlacedBy.HUMAN_APPROVAL)
    steps = (
        (AuditEventType.REQUEST_RECEIVED, AuditContext(profile_id="hotel-kitchen", facts={"text": "milk"})),
        (AuditEventType.OFFER_CREATED, AuditContext(offer=offer)),
        (AuditEventType.POLICY_EVALUATED, AuditContext(offer_id="off_1", option=option)),
        (AuditEventType.APPROVAL_REQUESTED, AuditContext(order=pending, approval=samples.approval())),
        (AuditEventType.APPROVAL_DECIDED,
         AuditContext(order=pending, approval=approval, approval_decision=samples.approve())),
        (AuditEventType.ORDER_CONFIRMED, AuditContext(order=ordered, approval=approval)),
        (AuditEventType.ORDER_BLOCKED, AuditContext(offer_id="off_1", option=option, decision=decision)),
    )
    events = [named_trail.record(event_type, samples.gateway, context) for event_type, context in steps]

    buyer = json.dumps([event.sentence for event in named_trail.view(AuditReader.BUYER, order_id="ord_1").events])
    stored = json.dumps([[event.data.supplier_sentence, event.data.supplier_facts] for event in events])
    shown = named_trail.view(AuditReader.SUPPLIER).model_dump_json()

    assert HOTEL_NAME in buyer  # the buyer does read its own name
    assert HOTEL_NAME not in stored and "Harbourside" not in shown
    assert "the amount is not shown" in stored  # and the rule is still named, with what is masked
