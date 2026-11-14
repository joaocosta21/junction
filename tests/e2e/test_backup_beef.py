"""The backup scenario (SPEC section 13): the hotel kitchen asks for 30 kg of beef chuck.

The sentence has no recording, so it is sent as its typed request. The beef is sold by variable weight in
steps of 3 kg, so the quantity is rounded up to the step, the total is a ceiling, and the order goes to a human
(P-06, the hotel's variable-weight rule).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from tta.contracts.common import OptionKind, OrderStatus, PlacedBy, Verdict

BEEF = "466988"  # Well Beef chuck roll, 109 kg confirmed, €16.88 per kg
LOT_STEP_KG = Decimal(3)
BEEF_EVENTS = [
    "request.received", "request.parsed", "lookup.performed", "offer.created", "policy.evaluated",
    "approval.requested", "approval.decided", "order.confirmed",
]


@pytest.mark.parametrize(("asked", "sold", "net"), [(30, 30, "506.40"), (31, 33, "557.04")])
def test_backup_typed_request_rounds_up_to_the_lot_step_and_the_total_is_a_ceiling(
    demo: Any, texts: Any, money: Any, fired: Any, lines_of: Any, asked: int, sold: int, net: str
) -> None:
    assert money(demo.product("hotel", BEEF)["allowed_lot_size"]) == LOT_STEP_KG

    best = demo.offer("hotel", texts.beef(asked))["options"][0]
    assert best["kind"] == OptionKind.BEST_CONFIRMED
    assert lines_of(best) == {BEEF: Decimal(sold)}
    assert lines_of(best)[BEEF] % LOT_STEP_KG == 0
    assert best["lines"][0]["variable_weight"] is True
    assert best["totals"]["is_ceiling"] is True
    assert money(best["totals"]["net"]) == Decimal(net)
    assert (best["decision"]["verdict"], fired(best)) == (Verdict.APPROVAL, {"P-06"})


def test_backup_typed_request_goes_to_a_human_and_is_ordered_with_a_ceiling(
    demo: Any, texts: Any, event_types: Any
) -> None:
    offer = demo.offer("hotel", texts.beef(30))
    order = demo.order("hotel", offer)
    assert order["status"] == OrderStatus.PENDING_APPROVAL

    decided = demo.approve_all_roles("hotel", order, "Kitchen will weigh it on arrival.")
    assert (decided["status"], decided["placed_by"]) == (OrderStatus.ORDERED, PlacedBy.HUMAN_APPROVAL)
    assert decided["option"]["totals"]["is_ceiling"] is True
    trail = demo.audit("hotel", order["order_id"])
    assert event_types(trail) == BEEF_EVENTS
    assert all(event["sentence"].strip() for event in trail["events"])
    assert {"P-06"} <= set(trail["events"][-1]["rule_ids"])
