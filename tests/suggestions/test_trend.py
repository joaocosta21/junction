"""The quantity trend: "your order has grown" (P15 R7, kind QUANTITY_TREND).

The last 6 orders of a product: the median of the last 3 against the median of the 3 before, a change of 15% or
more, and 4 of the 5 steps in one direction. Silent when the stored standing quantity is already within the
profile's drift tolerance of the recent median.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from decimal import Decimal
from typing import Any

import pytest

from tta.contracts.common import Unit
from tta.contracts.suggestion import Suggestion, SuggestionKind
from tta.suggestions import OrderHistory, quantity_trend

SCHOOL_OAT_DRINK = (60, 62, 66, 70, 74, 80, 84, 90)  # P15 section 4.6, the school kitchen's 8 weeks
STORED = Decimal(60)
TOLERANCE = Decimal("0.25")


def _trend(make_history: Callable[..., OrderHistory], litres: Sequence[int | str], *, stored: Decimal = STORED,
           tolerance: Decimal | None = TOLERANCE) -> Suggestion | None:
    history = make_history([{"470863": value} for value in litres])
    return quantity_trend(history, "470863", standing_order_id="so_school_weekly", stored_quantity=stored,
                          tolerance=tolerance)


def test_the_schools_oat_drink_has_grown_by_a_fifth_and_the_standing_order_still_says_60_litres(
    make_history: Callable[..., OrderHistory],
) -> None:
    found = _trend(make_history, SCHOOL_OAT_DRINK)

    assert found is not None
    assert (found.kind, found.product_id, found.quantity, found.unit) == (
        SuggestionKind.QUANTITY_TREND, "470863", Decimal(84), Unit.L,
    )
    assert found.standing_order_id == "so_school_weekly"
    assert found.accept_request is None  # accepting changes the stored quantity, a person's action
    assert found.evidence.values == (66, 70, 74, 80, 84, 90)
    assert found.evidence.thresholds == {
        "TREND_WINDOW": 6, "TREND_MIN_CHANGE": Decimal("0.15"), "TREND_MIN_STEPS_ONE_WAY": 4,
    }
    assert found.sentence == (
        "Your orders of Oatly oat drink (470863) are growing: about 84 L in your last 3 orders, 70 L in the 3 "
        "before. Your standing order still says 60 L. Renew once at 84 L? From a synthetic order history."
    )


def test_a_fall_is_said_as_a_fall(make_history: Callable[..., OrderHistory]) -> None:
    found = _trend(make_history, (90, 84, 80, 74, 70, 66), stored=Decimal(90))

    assert found is not None
    assert found.quantity == Decimal(70)
    assert "are shrinking: about 70 L in your last 3 orders, 84 L in the 3 before." in found.sentence


def test_four_steps_of_five_in_one_direction_are_enough(make_history: Callable[..., OrderHistory]) -> None:
    found = _trend(make_history, (60, 66, 64, 74, 80, 84), stored=Decimal(50))

    assert found is not None
    assert "are growing: about 80 L in your last 3 orders, 64 L in the 3 before." in found.sentence
    assert found.evidence.values == (60, 66, 64, 74, 80, 84)  # 4 of the 5 steps rise: the page's "Why?"


def test_a_mixed_direction_stays_silent(make_history: Callable[..., OrderHistory]) -> None:
    assert _trend(make_history, (70, 60, 80, 70, 90, 84)) is None


def test_a_change_below_15_percent_stays_silent(make_history: Callable[..., OrderHistory]) -> None:
    assert _trend(make_history, (70, 72, 74, 76, 78, 80)) is None


def test_a_stored_quantity_within_the_tolerance_of_the_recent_median_stays_silent(
    make_history: Callable[..., OrderHistory],
) -> None:
    assert _trend(make_history, SCHOOL_OAT_DRINK, stored=Decimal(80), tolerance=Decimal("0.1")) is None


def test_without_a_tolerance_only_a_stored_quantity_equal_to_the_recent_median_stays_silent(
    make_history: Callable[..., OrderHistory],
) -> None:
    assert _trend(make_history, SCHOOL_OAT_DRINK, stored=Decimal(84), tolerance=None) is None
    assert _trend(make_history, SCHOOL_OAT_DRINK, stored=Decimal(80), tolerance=None) is not None


def test_fewer_than_6_orders_stay_silent(make_history: Callable[..., OrderHistory]) -> None:
    assert _trend(make_history, (60, 66, 72, 80, 90)) is None


# --- Python review, item P11: a median of 0 raised InvalidOperation and cost the offer all its suggestions ------


class _ZeroHistory:
    """A history whose orders hold a quantity of 0, which the customer file's own check refuses: built by hand."""

    def __init__(self, values: Sequence[int]) -> None:
        from types import SimpleNamespace

        self._orders = [SimpleNamespace(quantities={"470863": Decimal(value)}) for value in values]

    def orders_with(self, product_id: str) -> list[Any]:
        return self._orders

    def unit_of(self, product_id: str) -> Unit:
        return Unit.L


@pytest.mark.parametrize("values", [(0, 0, 0, 10, 20, 30), (30, 20, 10, 0, 0, 0), (0, 0, 0, 0, 0, 0)])
def test_a_median_of_zero_gives_no_trend_and_does_not_raise(values: Sequence[int]) -> None:
    history: Any = _ZeroHistory(values)

    assert quantity_trend(history, "470863", standing_order_id="so", stored_quantity=STORED,
                          tolerance=TOLERANCE) is None
