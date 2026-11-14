"""Ordering alone, end to end in replay: the buyer's setting, off by default, on the real offers of the recording.

A browser's own kitchen is the one place a buyer can switch the setting on (`tta.api.sandbox`). Started from a
copy of the ward's profile and switched on, the ward's 200 litres are ordered by the agent alone, because every
statement is confirmed and no rule fires. Whatever is not confirmed still goes to a person.
Measured at the recording's own clock (Saturday 14 Nov 2026, 02:52 Helsinki time).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from tta.api.sandbox import KITCHEN_AGENT, KITCHEN_APPROVERS, Sandbox
from tta.api.wiring import Parts
from tta.contracts.common import ApproverRole, AvailabilityState, DecisionKind, OrderStatus, PlacedBy, Verdict
from tta.contracts.order import DecisionRequest
from tta.contracts.request import PurchaseRequest

KITCHEN_PURCHASING = next(one for one in KITCHEN_APPROVERS if ApproverRole.PURCHASING_MANAGER in one.roles)
PLACED_BY_AGENT = "tta.v1.order.placed_by_agent"


@pytest.fixture
def ward_request(scenario_2: dict[str, Any]) -> PurchaseRequest:
    """200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only."""
    return PurchaseRequest.model_validate(scenario_2)


def _ward_kitchen(parts: Parts, key: str, **settings: Any) -> Sandbox:
    book = parts.sandboxes.open(key)
    book.kitchen.start_from("allergy-ward")
    if settings:
        book.kitchen.set_up({**book.kitchen.settings, **settings})
    return book


def _event_types(book: Sandbox) -> list[str]:
    return [event.type for event in book.store.list_audit_events()]


def test_a_copy_of_a_shipped_profile_starts_with_ordering_alone_switched_off(parts: Parts) -> None:
    assert parts.sandboxes.open("fresh").kitchen.profile.auto_order_enabled is False
    assert _ward_kitchen(parts, "ward").kitchen.profile.auto_order_enabled is False


def test_settings_that_do_not_say_get_ordering_alone_switched_off(parts: Parts) -> None:
    book = parts.sandboxes.open("silent")
    unsaid = {name: value for name, value in book.kitchen.settings.items() if name != "auto_order_enabled"}

    assert book.kitchen.set_up(unsaid).auto_order_enabled is False


def test_with_the_setting_off_the_wards_200_litres_wait_for_a_person(
    parts: Parts, ward_request: PurchaseRequest
) -> None:
    book = _ward_kitchen(parts, "off")
    offer = book.service.create_offer(KITCHEN_AGENT, ward_request)

    order = book.service.place_order(KITCHEN_AGENT, offer.offer_id, offer.options[0].option_id, "k-1")

    assert (order.status, order.placed_by, order.decision.rule_ids) == (OrderStatus.PENDING_APPROVAL, None, ("F-10",))
    assert PLACED_BY_AGENT not in _event_types(book)
    decided = book.service.decide_approval(
        KITCHEN_PURCHASING, order.approval_id, DecisionRequest(decision=DecisionKind.APPROVE)
    )
    assert (decided.status, decided.placed_by) == (OrderStatus.ORDERED, PlacedBy.HUMAN_APPROVAL)


def test_with_the_setting_on_and_everything_confirmed_the_wards_200_litres_are_ordered_alone(
    parts: Parts, ward_request: PurchaseRequest
) -> None:
    book = _ward_kitchen(parts, "on", auto_order_enabled=True)
    offer = book.service.create_offer(KITCHEN_AGENT, ward_request)
    best = offer.options[0]

    order = book.service.place_order(KITCHEN_AGENT, offer.offer_id, best.option_id, "k-1")

    assert [(line.product_id, line.quantity) for line in best.lines] == [("464013", 200)]
    assert best.totals.net == Decimal("402.00")
    assert all(line.availability.state is AvailabilityState.CONFIRMED for line in best.lines)
    assert best.decision.verdict is Verdict.AUTO and best.decision.fired == ()
    assert (order.status, order.placed_by, order.approval_id) == (OrderStatus.ORDERED, PlacedBy.AGENT, None)
    assert order.decision.verdict is Verdict.AUTO and order.decision.fired == ()
    assert order.status_sentence == (
        "The agent placed this order alone for €402.00 net: no rule of profile my-kitchen asked for a human."
    )
    assert book.service.list_approvals(KITCHEN_PURCHASING) == ()
    assert _event_types(book)[-1] == PLACED_BY_AGENT


def test_with_the_setting_on_a_quantity_that_is_not_confirmed_still_goes_to_a_person(
    parts: Parts, scenario_1: dict[str, Any]
) -> None:
    """Scenario 1's alternative, 1,000 x 464306: Valio Aimo does not confirm the quantity (rule F-01)."""
    book = parts.sandboxes.open("unconfirmed")
    book.kitchen.set_up({**book.kitchen.settings, "auto_order_enabled": True, "max_order_net_eur": "3000"})
    offer = book.service.create_offer(KITCHEN_AGENT, PurchaseRequest.model_validate(scenario_1))
    unconfirmed = next(
        option for option in offer.options
        if any(line.availability.state is AvailabilityState.QUANTITY_NOT_CONFIRMED for line in option.lines)
    )

    order = book.service.place_order(KITCHEN_AGENT, offer.offer_id, unconfirmed.option_id, "k-1")

    assert [(line.product_id, line.quantity) for line in unconfirmed.lines] == [("464306", 1000)]
    assert unconfirmed.totals.net == Decimal("1010.00")
    assert (order.status, order.placed_by) == (OrderStatus.PENDING_APPROVAL, None)
    assert order.decision.rule_ids == ("F-01",)
    assert order.decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)
    assert PLACED_BY_AGENT not in _event_types(book)
