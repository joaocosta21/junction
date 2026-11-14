"""A renewal counts as history only when its order is found and ORDERED (review finding P12).

Before: a renewal whose order could not be found still counted, so a deleted or never-approved order moved the
baseline. Now it is left out, and the number left out can be said in a sentence.
In replay over tonight's capture, at the recording's own clock.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from tta.contracts.common import Identity
from tta.contracts.standing import Renewal
from tta.standing.demo import DEMO_STANDING_ORDER_ID, SYNTHETIC_WEEKS, load_demo
from tta.standing.history import not_counted_note, renewals_without_order, standing_history

HOTEL = "hotel-kitchen"


def _orphan(book, renewal_id: str, litres: int) -> Renewal:
    """A renewal that names an order the book does not hold."""
    last = book.store.list_renewals(DEMO_STANDING_ORDER_ID)[-1]
    line = last.lines[0].model_copy(update={"quantity": Decimal(litres)})
    renewal = Renewal(
        renewal_id=renewal_id, standing_order_id=DEMO_STANDING_ORDER_ID,
        renewed_at=last.renewed_at + timedelta(days=7), lines=(line,), offer_id=f"off_{renewal_id}",
        order_id=f"ord_{renewal_id}",
    )
    book.store.save_renewal(renewal)
    return renewal


def test_a_renewal_whose_order_cannot_be_found_is_left_out_and_counted_in_a_note(
    book, agent_hotel: Identity
) -> None:
    load_demo(book.standing, agent_hotel, book.replay)
    _orphan(book, "ren_gone", 900)

    history = standing_history(book.store, HOTEL, DEMO_STANDING_ORDER_ID)
    missing = renewals_without_order(book.store, HOTEL, DEMO_STANDING_ORDER_ID)

    assert [renewal.lines[0].quantity for renewal in history.renewals] == list(SYNTHETIC_WEEKS)
    assert missing == 1
    assert not_counted_note(missing) == "1 past renewal has no order record and was not counted."


def test_the_note_counts_each_one_and_says_nothing_when_every_order_is_found(book, agent_hotel: Identity) -> None:
    load_demo(book.standing, agent_hotel, book.replay)
    assert renewals_without_order(book.store, HOTEL, DEMO_STANDING_ORDER_ID) == 0
    assert not_counted_note(0) is None
    _orphan(book, "ren_gone_1", 900)
    second = _orphan(book, "ren_gone_2", 900)

    assert renewals_without_order(book.store, HOTEL, DEMO_STANDING_ORDER_ID) == 2
    assert renewals_without_order(
        book.store, HOTEL, DEMO_STANDING_ORDER_ID, excluding_offer_id=second.offer_id
    ) == 1  # the renewal being judged is no past renewal
    assert not_counted_note(2) == "2 past renewals have no order record and were not counted."
