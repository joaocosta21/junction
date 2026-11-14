"""Fixtures for the suggestions' tests: a factory of small synthetic order histories.

The product ids are real (tonight's recording); the names are short stand-ins so the sentences read in a test.
No test here loads the catalog, calls a live service or reads `.env`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import date, timedelta
from typing import Any

import pytest

from tta.contracts.customer import Customer
from tta.suggestions import OrderHistory, history_of

FIRST_MONDAY = date(2026, 9, 21)
WEEKLY = 7
# product id: (product type, unit) of the usual products a test history may name
USUAL: dict[str, tuple[str, str]] = {
    "469363": ("milk", "L"),
    "463047": ("milk", "L"),
    "463797": ("cream", "L"),
    "464615": ("yoghurt", "KG"),
    "464013": ("plant_drink", "L"),
    "473424": ("plant_drink", "L"),
    "470863": ("plant_drink", "L"),
    "466988": ("beef_chuck", "KG"),
}
NAMES = {
    "469363": "Arla milk",
    "463047": "Arla whole milk",
    "463797": "Arla cooking cream",
    "464615": "Valio greek yoghurt",
    "464013": "Alpro soya drink",
    "473424": "Alpro rice drink",
    "470863": "Oatly oat drink",
}


def build_customer(orders: Sequence[Mapping[str, Any]], *, start: date = FIRST_MONDAY, every: int = WEEKLY,
                   customer_id: str = "test-kitchen") -> Customer:
    named = sorted({product_id for order in orders for product_id in order})
    usual = [{"product_id": product_id, "product_type": USUAL[product_id][0], "unit": USUAL[product_id][1],
              "use": "SERVED"} for product_id in named or ["469363"]]
    history = [{"delivered_on": start + timedelta(days=every * week), "quantities": dict(order)}
               for week, order in enumerate(orders)]
    return Customer.model_validate({
        "customer_id": customer_id, "synthetic": True, "name": "Test Kitchen", "kind": "Hotel kitchen",
        "contact": {"name": "Test Person", "title": "Chef"}, "people": {"purchasing_manager": "Test Person"},
        "usual": usual, "history": history,
    })


@pytest.fixture
def make_history() -> Callable[..., OrderHistory]:
    """`make_history([{"469363": 100, "463797": 10}, ...])`: one weekly order per mapping, oldest first."""

    def make(orders: Sequence[Mapping[str, Any]], *, names: Mapping[str, str] | None = None,
             **options: Any) -> OrderHistory:
        return history_of(build_customer(orders, **options), NAMES if names is None else names)

    return make
