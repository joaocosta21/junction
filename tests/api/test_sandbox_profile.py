""""My kitchen": one custom buyer profile per browser's order book (task FEAT-1).

Scores on the 20% "autonomy and controls" and on Core 3 of the brief, "what the agent may decide on its own, and
what must go to a human for sign-off": a visitor sets its own kitchen's limits, checked as a profile file is, and
the agent orders alone within them. The profile lives in the visitor's own book only: the shared book of the
tokens, the policy files and every other visitor never see it.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from tta.api.sandbox import (
    KITCHEN_AGENT,
    KITCHEN_APPROVERS,
    KITCHEN_PROFILE_ID,
    MAX_EXCLUDED_ALLERGENS,
    Kitchen,
    Sandbox,
)
from tta.api.wiring import Parts
from tta.contracts.common import ApproverRole, DecisionKind, Identity, OrderStatus, Verdict
from tta.contracts.errors import NotAuthorised, NotFound
from tta.contracts.order import DecisionRequest, Order
from tta.contracts.request import PurchaseRequest
from tta.policy import PolicyLoadError, RulePolicyEngine

KITCHEN_PURCHASING = next(one for one in KITCHEN_APPROVERS if ApproverRole.PURCHASING_MANAGER in one.roles)


@pytest.fixture
def milk(scenario_1: dict[str, Any]) -> PurchaseRequest:
    return PurchaseRequest.model_validate(scenario_1)


def _settings(kitchen: Kitchen, **change: Any) -> dict[str, Any]:
    """The kitchen's settings as they stand, with some changed: what the page sends."""
    return {**kitchen.settings, **change}


def _order_milk(book: Sandbox, agent: Identity, request: PurchaseRequest, key: str) -> Order:
    offer = book.service.create_offer(agent, request)
    return book.service.place_order(agent, offer.offer_id, offer.options[0].option_id, key)


def test_a_new_book_starts_with_a_copy_of_the_hotel_kitchen_under_its_own_id_and_hash(parts: Parts) -> None:
    book = parts.sandboxes.open("visitor-one")
    hotel = RulePolicyEngine.from_files().get_profile("hotel-kitchen")

    profile = book.kitchen.profile
    authority = book.service.get_authority(KITCHEN_AGENT)

    assert (profile.profile_id, profile.display_name, book.kitchen.started_from) == (
        KITCHEN_PROFILE_ID, "My kitchen", "hotel-kitchen"
    )
    assert (profile.max_order_net_eur, profile.max_daily_net_eur) == (hotel.max_order_net_eur, hotel.max_daily_net_eur)
    assert not book.kitchen.is_set_up
    assert authority.profile == profile and authority.policy_hash != parts.policy.policy_hash(hotel)
    assert {approver.id for approver in KITCHEN_APPROVERS} == {
        holder for holders in profile.approver_roles.values() for holder in holders
    }


def test_scenario_1_requires_approval_at_both_spend_limits(
    parts: Parts, milk: PurchaseRequest, agent_hotel: Identity
) -> None:
    generous, careful = parts.sandboxes.open("generous"), parts.sandboxes.open("careful")
    generous.kitchen.set_up(_settings(generous.kitchen, max_order_net_eur="3000"))
    careful.kitchen.set_up(_settings(careful.kitchen, max_order_net_eur="750"))

    alone = _order_milk(generous, KITCHEN_AGENT, milk, "k-1")
    to_a_human = _order_milk(careful, KITCHEN_AGENT, milk, "k-1")
    hotel = _order_milk(generous, agent_hotel, milk, "k-2")  # the hotel's own agent in the same browser

    assert (alone.status, alone.decision.verdict, str(alone.decision.policy_hash)) == (
        OrderStatus.PENDING_APPROVAL, Verdict.APPROVAL, generous.service.get_authority(KITCHEN_AGENT).policy_hash
    )
    # Without coffee milk the confirmed stock covers 435 of the 1,000 litres: the fill rule fires as well (P-03).
    assert alone.profile_id == KITCHEN_PROFILE_ID and alone.option.totals.net == Decimal("1083.39")
    assert [(line.product_id, line.quantity) for line in alone.option.lines] == [("469363", 384), ("462775", 51)]
    assert alone.decision.rule_ids == ("P-03",)  # within the €3,000 limit; 43.5% covered, below the 90% minimum
    assert (to_a_human.status, to_a_human.decision.rule_ids) == (OrderStatus.PENDING_APPROVAL, ("P-01", "P-03"))
    assert to_a_human.decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)
    assert (hotel.status, hotel.decision.rule_ids, hotel.profile_id) == (
        OrderStatus.PENDING_APPROVAL, ("P-01", "P-03"), "hotel-kitchen"
    )


def test_one_books_kitchen_never_changes_another_books_offers(parts: Parts, milk: PurchaseRequest) -> None:
    one, other = parts.sandboxes.open("visitor-one"), parts.sandboxes.open("visitor-two")
    one.kitchen.set_up(_settings(one.kitchen, max_order_net_eur="3000", display_name="Visitor one's kitchen"))

    there = _order_milk(other, KITCHEN_AGENT, milk, "k-1")

    assert other.kitchen.profile.display_name == "My kitchen"
    assert (there.status, there.decision.rule_ids) == (OrderStatus.PENDING_APPROVAL, ("P-01", "P-03"))
    assert one.service.list_orders(KITCHEN_AGENT) == ()


def test_the_kitchen_never_reaches_the_shared_book_of_the_tokens_or_the_policy_files(
    parts: Parts, milk: PurchaseRequest
) -> None:
    book = parts.sandboxes.open("visitor-one")
    book.kitchen.set_up(_settings(book.kitchen, max_order_net_eur="3000"))
    _order_milk(book, KITCHEN_AGENT, milk, "k-1")

    with pytest.raises(NotAuthorised):
        parts.service.get_authority(KITCHEN_AGENT)
    with pytest.raises(NotAuthorised):
        parts.service.create_offer(KITCHEN_AGENT, milk)
    assert KITCHEN_PROFILE_ID not in parts.policy.profile_ids()
    assert KITCHEN_PROFILE_ID not in RulePolicyEngine.from_files().profile_ids()
    assert parts.store.list_audit_events() == ()


def test_the_kitchens_approval_is_decided_by_its_own_approvers_and_by_no_hotel_approver(
    parts: Parts, milk: PurchaseRequest, approver_purchasing: Identity
) -> None:
    book = parts.sandboxes.open("visitor-one")
    waiting = _order_milk(book, KITCHEN_AGENT, milk, "k-1")
    approve = DecisionRequest(decision=DecisionKind.APPROVE, option_id=waiting.option_id)

    with pytest.raises(NotFound):  # another buyer's approval reads as one nobody issued
        book.service.decide_approval(approver_purchasing, waiting.approval_id, approve)
    decided = book.service.decide_approval(KITCHEN_PURCHASING, waiting.approval_id, approve)

    assert decided.status is OrderStatus.ORDERED
    stored = [event for event in book.store.list_audit_events() if event.data.order_id == waiting.order_id]
    assert stored and {event.data.profile_id for event in stored} == {KITCHEN_PROFILE_ID}
    assert {event.data.policy_hash for event in stored if event.data.policy_hash} == {waiting.decision.policy_hash}
    assert book.service.get_audit(KITCHEN_AGENT, order_id=waiting.order_id).events  # the buyer's own view


def test_starting_again_brings_back_the_copy_of_the_hotel_kitchen(parts: Parts) -> None:
    book = parts.sandboxes.open("visitor-one")
    book.kitchen.set_up(_settings(book.kitchen, max_order_net_eur="3000"))

    parts.sandboxes.drop("visitor-one")
    again = parts.sandboxes.open("visitor-one")

    assert again.kitchen.profile.max_order_net_eur == 750 and not again.kitchen.is_set_up


def test_a_kitchen_starts_from_a_copy_of_either_demo_profile_and_of_nothing_else(parts: Parts) -> None:
    kitchen = parts.sandboxes.open("visitor-one").kitchen

    ward = kitchen.start_from("allergy-ward")

    assert (ward.profile_id, ward.excluded_allergens, ward.require_confirmed) == (
        KITCHEN_PROFILE_ID, ("AM", "AW"), True
    )
    assert kitchen.started_from == "allergy-ward"
    with pytest.raises(PolicyLoadError):
        kitchen.start_from("my-kitchen")


@pytest.mark.parametrize(
    ("change", "named"),
    [
        ({"max_order_net_eur": "100000.01"}, "max_order_net_eur"),
        ({"max_daily_net_eur": "-1"}, "max_daily_net_eur"),
        ({"min_fill_ratio": "2"}, "min_fill_ratio"),
        ({"excluded_allergens": ["AM"], "allergen_strictness": None}, "allergen_strictness"),
        ({"excluded_allergens": ["AE", "AF", "AM", "AN", "AP", "AS", "AU", "AW", "AY", "BC", "BM"],
          "allergen_strictness": "STRICT"}, "excluded_allergens"),
        ({"excluded_allergens": ["X99"], "allergen_strictness": "STRICT"}, "excluded_allergens"),
        ({"display_name": "   "}, "display_name"),
        ({"F-01": "off"}, "fixed rule F-01"),
        ({"variable_weight": "F-07"}, "fixed rule F-07"),
        ({"approver_roles": {"purchasing_manager": ["agent:my-kitchen"]}}, "approver_roles"),
        ({"profile_id": "hotel-kitchen"}, "profile_id"),
        ({"max_unit_price_eur": "10"}, "max_unit_price_eur"),
    ],
)
def test_a_setting_out_of_bounds_or_not_of_the_page_is_refused_and_named(
    parts: Parts, change: dict[str, Any], named: str
) -> None:
    kitchen = parts.sandboxes.open("visitor-one").kitchen
    before = kitchen.profile

    with pytest.raises(PolicyLoadError) as refused:
        kitchen.set_up(_settings(kitchen, **change))

    assert named in str(refused.value)
    assert kitchen.profile == before and not kitchen.is_set_up
    assert MAX_EXCLUDED_ALLERGENS == 10
