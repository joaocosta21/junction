"""The path on which the agent orders alone: a buyer setting, off in every shipped profile (rule F-10).

Every other order test runs on the shipped profiles, where no order is placed without a person. Here the two
profiles are loaded with the setting switched on, as a buyer would switch it on for its own kitchen.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from tta.contracts.common import ApproverRole, Identity, OrderStatus, PlacedBy, Verdict
from tta.contracts.errors import NotAuthorised
from tta.contracts.offer import OfferOption
from tta.contracts.policy import BuyerProfile, PolicyContext, PolicyDecision
from tta.policy import PROFILES_DIR, RULES_PATH, RulePolicyEngine, load_profiles
from tta.policy.loading import load_rulebook

KEY = "alone-1"
WARD = "allergy-ward"


@pytest.fixture(scope="module")
def shipped() -> RulePolicyEngine:
    return RulePolicyEngine.from_files()


@pytest.fixture(scope="module")
def engine() -> RulePolicyEngine:
    """The shipped rules with both profiles switched on. Replaces the folder's engine for this module's `book`."""
    rulebook = load_rulebook(RULES_PATH)
    profiles = load_profiles(PROFILES_DIR, rulebook.fixed_rule_ids).values()
    return RulePolicyEngine(rulebook, [profile.model_copy(update={"auto_order_enabled": True}) for profile in profiles])


def test_with_the_setting_on_a_confirmed_ward_order_within_every_limit_is_placed_by_the_agent(
    book: Any, samples: Any, agent_ward: Identity
) -> None:
    offer = book.offer(samples.ward_safe(), profile_id=WARD)

    order = book.service.place_order(offer.offer_id, "opt_1", agent_ward, KEY)

    assert order.status is OrderStatus.ORDERED and order.placed_by is PlacedBy.AGENT
    assert order.approval_id is None and book.store.list_approvals() == ()
    assert order.decision.verdict is Verdict.AUTO and order.decision.fired == ()
    assert order.option.decision == order.decision
    # Why it was allowed, from the values the order-time check read, and no rule id (check C1-9 of 15 Nov 2026).
    assert order.status_sentence == (
        "The agent placed this order alone for €428.00 net. That was allowed: ordering alone is switched on for City "
        "Hospital, Ward 4; the total of €428.00 is within the €500 limit per order; today's spend with this order "
        "is €428.00 of the €1,500 limit per day; every statement of the offer is confirmed; and no rule asked for a "
        "person."
    )
    assert book.store.get_order(order.order_id) == order
    assert book.event_types() == ["order.placed_by_agent"]


def test_the_log_entry_of_an_order_placed_alone_carries_why_it_was_allowed_with_the_days_total(
    book: Any, samples: Any, agent_ward: Identity
) -> None:
    """The second order of the day: the day's total is the first order's €428.00 and this one's."""
    first = book.offer(samples.ward_safe(), profile_id=WARD)
    book.service.place_order(first.offer_id, "opt_1", agent_ward, "alone-first")
    offer = book.offer(samples.ward_safe(), profile_id=WARD)

    order = book.service.place_order(offer.offer_id, "opt_1", agent_ward, KEY)

    assert order.placed_by is PlacedBy.AGENT
    assert "today's spend with this order is €856.00 of the €1,500 limit per day" in order.status_sentence
    (event,) = book.events(order.order_id)
    facts = event.data.facts
    assert facts["order"]["status_sentence"] == order.status_sentence
    assert facts["decision"]["verdict"] == "AUTO" and facts["decision"]["fired"] == []
    assert facts["decision"]["sentence"] == (
        "The agent may place this order alone: ordering alone is switched on for City Hospital, Ward 4; the total "
        "of €428.00 before tax is within the €500 limit per order; today's spend with this order would be €856.00 "
        "of the €1,500 limit per day; 100% of the requested quantity is covered; every statement of the offer is "
        "confirmed; and no rule asks for a person."
    )
    for sentence in (order.status_sentence, facts["decision"]["sentence"]):
        assert not re.search(r"\b[FP]-\d\d\b", sentence), sentence  # a person reads these: no rule id
    # Valio Aimo's view of the same entry holds no limit amount and no name of the buyer.
    shown = f"{event.data.supplier_sentence} {event.data.supplier_facts}"
    assert "€500" not in shown and "€1,500" not in shown and "City Hospital" not in shown


def test_with_the_setting_on_a_quantity_that_is_not_confirmed_still_waits_for_a_person(
    book: Any, samples: Any, agent_hotel: Identity
) -> None:
    offer = book.offer(samples.unconfirmed("opt_1"))

    order = book.service.place_order(offer.offer_id, "opt_1", agent_hotel, KEY)

    assert order.status is OrderStatus.PENDING_APPROVAL and order.placed_by is None
    assert "F-01" in order.decision.rule_ids and "F-10" not in order.decision.rule_ids
    assert ApproverRole.PURCHASING_MANAGER in book.store.get_approval(order.approval_id).required_roles
    assert "order.placed_by_agent" not in book.event_types()


def test_with_the_setting_on_an_order_above_the_buyers_limit_still_waits_for_a_person(
    book: Any, samples: Any, agent_hotel: Identity
) -> None:
    offer = book.offer(samples.above_order_limit())

    order = book.service.place_order(offer.offer_id, "opt_1", agent_hotel, KEY)

    assert order.status is OrderStatus.PENDING_APPROVAL and order.decision.rule_ids == ("P-01",)


class _SaysAuto:
    """A policy engine that forgets F-10: it judges with the setting on, whatever the caller's profile says."""

    def __init__(self, shipped: RulePolicyEngine, switched_on: RulePolicyEngine) -> None:
        self._shipped = shipped
        self._switched_on = switched_on

    def evaluate(self, option: OfferOption, profile: BuyerProfile, context: PolicyContext) -> PolicyDecision:
        return self._switched_on.evaluate(option, profile.model_copy(update={"auto_order_enabled": True}), context)

    def __getattr__(self, name: str) -> object:
        return getattr(self._shipped, name)


def test_the_order_service_keeps_a_person_on_the_order_when_the_policy_engine_forgets_the_setting(
    book: Any, samples: Any, agent_ward: Identity, shipped: RulePolicyEngine, engine: RulePolicyEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The second place F-10 is applied (`tta.orders.checking`): the shipped ward profile has the setting off."""
    forgetful = _SaysAuto(shipped, engine)
    monkeypatch.setattr(book.policy, "_engine", forgetful)
    offer = book.offer(samples.ward_safe(), profile_id=WARD)
    assert forgetful.evaluate(samples.ward_safe(), shipped.get_profile(WARD), _context(book)).verdict is Verdict.AUTO

    order = book.service.place_order(offer.offer_id, "opt_1", agent_ward, KEY)

    assert order.status is OrderStatus.PENDING_APPROVAL and order.placed_by is None
    assert order.decision.rule_ids == ("F-10",)
    assert book.store.get_approval(order.approval_id).required_roles == (ApproverRole.PURCHASING_MANAGER,)


def _context(book: Any) -> PolicyContext:
    return PolicyContext(now=book.clock.now(), day_committed_net_eur=0)


def test_on_the_shipped_profiles_the_same_ward_order_waits_for_the_purchasing_manager(
    samples: Any, agent_ward: Identity, shipped: RulePolicyEngine, book: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(book.policy, "_engine", shipped)
    offer = book.offer(samples.ward_safe(), profile_id=WARD)

    order = book.service.place_order(offer.offer_id, "opt_1", agent_ward, KEY)

    assert order.status is OrderStatus.PENDING_APPROVAL and order.decision.rule_ids == ("F-10",)


# --- who completes an approval when F-10 is the only rule left (review C1, fix X5) --------------------------

def test_a_plain_f10_approval_is_signed_by_the_purchasing_manager_and_by_no_other_role(
    book: Any, samples: Any, agent_ward: Identity, shipped: RulePolicyEngine, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(book.policy, "_engine", shipped)
    waiting = book.waiting(agent_ward, samples.ward_safe(), profile_id=WARD)
    dietitian = samples.approver("human:ward-dietitian", WARD, ApproverRole.DIETITIAN)
    purchasing = samples.approver("human:ward-purchasing", WARD, ApproverRole.PURCHASING_MANAGER)

    with pytest.raises(NotAuthorised, match="still needs the purchasing manager"):
        book.service.decide(waiting.approval_id, dietitian, samples.approve())
    decided = book.service.decide(waiting.approval_id, purchasing, samples.approve())

    assert decided.status is OrderStatus.ORDERED and decided.placed_by is PlacedBy.HUMAN_APPROVAL
