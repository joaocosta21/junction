"""The first page's five examples in one order book, in any order (review A4, finding H2), in replay at the
recording's clock (Saturday 14 Nov 2026 02:52, Helsinki).

Before B0 the hotel's four examples came to EUR 3,102.64 and the fifth was sent to finance because the earlier
ones were waiting. With coffee milk out of scenario 1 they come to EUR 1,605.39 of the hotel's EUR 3,000 a day, so
no order of the five meets the limit per day, whichever comes first. A waiting order still counts (AIMO/PLAN.md,
decision 9): asked twice, the examples do pass the limit, and the approval then says how much of the day is
ordered and how much is waiting.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from tta.api.wiring import Parts
from tta.contracts.common import Identity, OrderStatus
from tta.contracts.order import Order
from tta.contracts.request import PurchaseRequest

MONDAY = "2026-11-16"
HOTEL, WARD = "hotel", "ward"
# The typed requests of `tta.ui.examples.EXAMPLES`, written out: the pages are not loaded in this folder.
EXAMPLES: tuple[tuple[str, str, dict[str, Any]], ...] = (
    ("scenario-1", HOTEL, {"lines": [{"text": "1,000 litres of lactose-free milk by Monday", "product_type": "milk",
                                      "required_claims": ["FREE_FROM_LACTOSE"], "quantity": 1000, "unit": "L"}]}),
    ("scenario-2", WARD, {"require_confirmed": True, "lines": [{
        "text": "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only",
        "product_type": "plant_drink", "quantity": 200, "unit": "L", "exclude_allergens": ["AM", "AW"]}]}),
    ("scenario-3", HOTEL, {"lines": [{"text": "100 litres of Oddlygood Barista oat drink, product 473609, by Monday",
                                      "product_ids": ["473609"], "quantity": 100, "unit": "L"}]}),
    ("scenario-4", HOTEL, {"lines": [{
        "text": "100 litres of Elovena barista oat drink, product 469512, by Monday; no milk, strict rule",
        "product_ids": ["469512"], "quantity": 100, "unit": "L", "exclude_allergens": ["AM"],
        "allergen_strictness": "STRICT"}]}),
    ("scenario-5", HOTEL, {"prefer": "RELIABILITY", "lines": [{
        "text": "100 litres of oat drink by Monday, most reliable delivery", "product_type": "plant_drink",
        "name_terms": ["oat"], "quantity": 100, "unit": "L"}]}),
)
ORDERS = {
    "in order": (0, 1, 2, 3, 4), "backwards": (4, 3, 2, 1, 0), "the large one last": (1, 2, 3, 4, 0),
    "the large one in the middle": (4, 2, 0, 3, 1),
}
DAY_RULE = "P-02"


def _run(parts: Parts, agents: dict[str, Identity], index: int, key: str) -> Order:
    name, who, body = EXAMPLES[index]
    request = PurchaseRequest.model_validate({"needed_by": MONDAY, **body})
    offer = parts.service.create_offer(agents[who], request)
    return parts.service.place_order(agents[who], offer.offer_id, offer.options[0].option_id, f"{name}-{key}")


@pytest.fixture
def agents(agent_hotel: Identity, agent_ward: Identity) -> dict[str, Identity]:
    return {HOTEL: agent_hotel, WARD: agent_ward}


def _eur(value: Decimal) -> str:
    return f"€{value:,.2f}"


@pytest.mark.parametrize("order", list(ORDERS.values()), ids=list(ORDERS))
def test_the_five_examples_in_any_order_never_meet_the_limit_per_day(
    parts: Parts, agents: dict[str, Identity], order: tuple[int, ...]
) -> None:
    placed = {EXAMPLES[index][0]: _run(parts, agents, index, "once") for index in order}

    assert all(DAY_RULE not in one.decision.rule_ids for one in placed.values())
    assert all(one.status is OrderStatus.PENDING_APPROVAL for one in placed.values())  # ordering alone is off
    assert all("finance" not in one.status_sentence for one in placed.values())
    hotel = sum(placed[name].option.totals.net for name, who, _ in EXAMPLES if who == HOTEL)
    assert placed["scenario-1"].option.totals.net == Decimal("1083.39")  # B0: coffee milk is out of scenario 1
    # Measured on B0's tree: 1,083.39 + 174.00 + 208.00 + 140.00 = 1,605.39 of the hotel's 3,000 a day.
    assert hotel < parts.service.get_authority(agents[HOTEL]).profile.max_daily_net_eur == 3000


def test_asked_twice_the_day_is_full_and_the_approval_says_what_is_ordered_and_what_is_waiting(
    parts: Parts, agents: dict[str, Identity]
) -> None:
    first = [_run(parts, agents, index, "first") for index in (0, 2, 3, 4)]
    again = _run(parts, agents, 0, "second")  # on B0's tree 1,605.39 waiting + 1,083.39 = 2,688.78: under 3,000
    waiting = sum((one.option.totals.net for one in (*first, again)), Decimal(0))

    over = _run(parts, agents, 0, "third")  # 2,688.78 waiting + 1,083.39 = 3,772.17

    assert DAY_RULE not in again.decision.rule_ids and DAY_RULE in over.decision.rule_ids
    approval = next(one for one in parts.store.list_approvals() if one.approval_id == over.approval_id)
    assert (
        f"Before this order, today's spend of this buyer is {_eur(waiting)} before tax: €0.00 ordered and "
        f"{_eur(waiting)} waiting for approval. A waiting order counts until a person rejects it or its time to "
        "decide passes."
    ) in approval.reasons
