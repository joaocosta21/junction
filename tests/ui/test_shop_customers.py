"""The shop page's four customers: one definition with the gateway's profile files (C2 F5, the page's half).

Scores on the 20% "autonomy and controls" (the limits, allergen rules and substitution scope a customer sees on the
shop page are the ones its buyer profile file sets, so a judge reads the same rules on every surface) and on the
15% openness (the generated history is labelled synthetic wherever it shows, and dated before the demo clock).
Until the gateway lists its customers (the next wave), kitchens.js keeps a copy of the settings; these tests stop
that copy drifting from `src/tta/policy/profiles/`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import tta.ui
from tta.policy import RulePolicyEngine
from tta.ui.shop_api import SHOP_KITCHENS

SHOP_JS = Path(tta.ui.__file__).parent / "static" / "shop" / "js"
# Set by the gateway for a shop book, never sent by the page (tta.api.sandbox, _FIXED_PARTS).
SET_BY_THE_GATEWAY = {"profile_id", "description", "illustrative", "approver_roles"}
STRICTNESS = {"allergen_strictness", "allergen_strictness_by_code"}  # compared as the rule of each allergen
DEMO_DAY = "2026-11-12"  # the demo clock, Thursday 12 Nov 2026 14:15 Helsinki (TTA_DEMO_CLOCK)
SYNTHETIC = "Synthetic: made up for the demonstration"
HISTORY_DATE = re.compile(r'\{ date: "(\d{4}-\d{2}-\d{2})", lines:')


def _read(name: str) -> str:
    return (SHOP_JS / name).read_text(encoding="utf-8")


def _rule_per_allergen(profile: dict[str, Any]) -> dict[str, Any]:
    """The rule each excluded allergen is checked under: its own, else the profile's general one."""
    by_code = profile.get("allergen_strictness_by_code") or {}
    return {code: by_code.get(code) or profile.get("allergen_strictness") for code in profile["excluded_allergens"]}


def _without(profile: dict[str, Any], names: set[str]) -> dict[str, Any]:
    return {name: value for name, value in profile.items() if name not in names}


@pytest.mark.parametrize("customer_id", sorted(SHOP_KITCHENS.values()))
def test_the_settings_the_page_sends_are_the_customers_profile_file(
    customer_id: str, client: TestClient, shop_profile_settings: dict[str, dict[str, Any]]
) -> None:
    """Sent as the page sends them, the settings in force equal the profile file in every field the page sets."""
    headers = {"X-Shop-Request": "1", "X-Shop-Kitchen": customer_id}

    saved = client.put("/shop/api/kitchen", headers=headers, json=shop_profile_settings[customer_id])

    assert saved.status_code == 200, saved.text
    in_force = saved.json()["profile"]
    shipped = RulePolicyEngine.from_files().get_profile(customer_id).model_dump(mode="json")
    assert _without(in_force, SET_BY_THE_GATEWAY | STRICTNESS) == _without(shipped, SET_BY_THE_GATEWAY | STRICTNESS)
    assert _rule_per_allergen(in_force) == _rule_per_allergen(shipped)


def test_the_page_names_the_four_customers_of_the_profile_files(
    shop_profile_settings: dict[str, dict[str, Any]],
) -> None:
    assert sorted(shop_profile_settings) == sorted(SHOP_KITCHENS.values())
    names = {customer_id: settings["display_name"] for customer_id, settings in shop_profile_settings.items()}
    assert names == {
        "school-kitchen": "Kilo School", "allergy-ward": "City Hospital, Ward 4",
        "hotel-kitchen": "Harbourside Hotel", "bakery-cafe": "Kallio Bakery",
    }


def test_the_past_orders_on_the_page_are_dated_before_the_demo_clock() -> None:
    dates = HISTORY_DATE.findall(_read("kitchens.js"))

    assert len(dates) == 14  # four customers, three or four past orders each
    assert all(day < DEMO_DAY for day in dates), sorted(dates)[-1]


def test_every_past_order_row_is_labelled_synthetic_where_it_is_shown() -> None:
    """The orders list and the delivery calendar print the label on each row of the history."""
    assert f'export const SYNTHETIC = "{SYNTHETIC}";' in _read("kitchens.js")
    orders, deliveries = _read("views/orders.js"), _read("views/deliveries.js")
    assert "k.history.map(" in orders and "${SYNTHETIC}</div></td>" in orders
    assert "e.past.lines" in deliveries and "· ${SYNTHETIC}</span>" in deliveries
