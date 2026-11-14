"""Fixtures for the menu planner's tests: the gateway in replay over tonight's capture, the shipped recipes.

Every test gets its own parts, so the rate limits and the order book start empty. The catalog is built once.
No test here calls a live service, and nothing reads `.env`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from typing import Any

import pytest

from tta.api.limits import RateLimit
from tta.api.wiring import Parts, build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.menu import MenuRequest
from tta.menus import Recipe, load_recipes

MONDAY = "2026-11-16"  # the Monday after tonight's capture (Saturday 14 Nov 2026 02:52 server time)
MANY_CALLS = RateLimit(calls=1000)

# The demo case (task MENU-1, "last-minute event"): a booking on Saturday night for a dinner on Monday, with
# confirmed stock only. The kitchen holds butter and sugar. Plain quark cannot be had by Monday in the capture.
LAST_MINUTE_EVENT: dict[str, Any] = {
    "dishes": [{"dish_id": "beef_stew", "servings": 120}, {"dish_id": "berry_quark_dessert", "servings": 120}],
    "stock": [{"product_type": "butter", "quantity": 3, "unit": "KG"},
              {"product_type": "sugar", "quantity": 2, "unit": "KG"}],
    "needed_by": MONDAY,
    "require_confirmed": True,
}


@pytest.fixture(scope="session")
def catalog() -> ProductCatalog:
    return ProductCatalog.from_settings(Settings.for_tests())


@pytest.fixture(scope="session")
def recipes(catalog: ProductCatalog) -> Mapping[str, Recipe]:
    return load_recipes(catalog.product_type_keys())


@pytest.fixture
def parts(settings: Settings, catalog: ProductCatalog) -> Iterator[Parts]:
    built = build_parts(settings, catalog=catalog, rate_limit=MANY_CALLS)
    yield built
    built.close()


@pytest.fixture(scope="session")
def menu() -> Callable[..., MenuRequest]:
    def build(**changes: Any) -> MenuRequest:
        return MenuRequest.model_validate({**LAST_MINUTE_EVENT, **changes})

    return build
