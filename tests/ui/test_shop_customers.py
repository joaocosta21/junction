"""The shop page's four customers: one definition with the gateway's profile and customer files (C2 F5, the page's
half).

Scores on the 20% "autonomy and controls" (the limits, allergen rules and substitution scope a customer sees on the
shop page are the ones its buyer profile file sets, and the people who sign are the customer file's, so a judge reads
the same rules and the same names on every surface) and on the 15% openness (the generated history is labelled
synthetic wherever it shows, and dated before the demo clock). The page reads who the customer is, who signs, its
usual products and its past orders from `GET /shop/api/customer`; kitchens.js keeps the settings it sends (checked
here against `src/tta/policy/profiles/`) and presentation only: the colour, the kind of customer, the examples.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import tta.ui
from tta.customers import shipped_customers
from tta.policy import RulePolicyEngine
from tta.ui.shop_api import SHOP_KITCHENS

SHOP_JS = Path(tta.ui.__file__).parent / "static" / "shop" / "js"
# Set by the gateway for a shop book, never sent by the page (tta.api.sandbox, _FIXED_PARTS).
SET_BY_THE_GATEWAY = {"profile_id", "description", "illustrative", "approver_roles"}
STRICTNESS = {"allergen_strictness", "allergen_strictness_by_code"}  # compared as the rule of each allergen
DEMO_DAY = "2026-11-12"  # the demo clock, Thursday 12 Nov 2026 14:15 Helsinki (TTA_DEMO_CLOCK)
SYNTHETIC = "Synthetic: made up for the demonstration"
# What the customer file holds and the page no longer types in: people, who signs, past orders, the customer's details.
TYPED_IN = re.compile(r"^\s*(person|people|roles|history|customerNo|address|deliveryDays|detail):", re.MULTILINE)
PRESENTED_KIND = re.compile(r'customerId: "([a-z-]+)",\s*kind: "([^"]+)"')
HEADERS = {"X-Shop-Request": "1"}


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
    headers = {**HEADERS, "X-Shop-Kitchen": customer_id}

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


# --- who the customer is comes from the gateway, not from kitchens.js --------------------------------------------


def test_the_page_types_in_no_person_role_past_order_or_customer_detail() -> None:
    """Until the customer route answers, the page has nobody to name and no history to show (nothing invented)."""
    kitchens = _read("kitchens.js")

    assert TYPED_IN.findall(kitchens) == []
    assert "Päivi Korhonen" not in kitchens and "Hanna Laine" not in kitchens and "Marko Heikkinen" not in kitchens


def test_the_page_reads_its_customer_from_the_customer_route() -> None:
    assert 'call(kitchen, "GET", "/customer")' in _read("api.js")
    reader = _read("customer.js")
    assert ".customer()" in reader and "contact" in reader and "people" in reader and "history" in reader


def test_each_customers_kind_on_the_page_is_its_customer_files(
    shop_profile_settings: dict[str, dict[str, Any]],
) -> None:
    presented = dict(PRESENTED_KIND.findall(_read("kitchens.js")))
    files = shipped_customers()

    assert sorted(presented) == sorted(SHOP_KITCHENS.values())
    assert presented == {customer_id: files[customer_id].kind for customer_id in presented}
    # The name the page shows is the profile's display name, which equals the customer file's name.
    names = {customer_id: shop_profile_settings[customer_id]["display_name"] for customer_id in presented}
    assert names == {customer_id: files[customer_id].name for customer_id in presented}


@pytest.mark.parametrize("kitchen", sorted(SHOP_KITCHENS))
def test_the_customer_route_gives_the_page_its_people_and_a_history_dated_before_the_demo_clock(
    kitchen: str, client: TestClient
) -> None:
    answer = client.get("/shop/api/customer", headers={**HEADERS, "X-Shop-Kitchen": kitchen})

    assert answer.status_code == 200, answer.text
    view = answer.json()
    customer = view["customer"]
    assert customer["contact"]["name"] in customer["people"].values()
    days = [order["delivered_on"] for order in customer["history"]]
    assert days and all(day < DEMO_DAY for day in days), max(days)
    assert view["note"].startswith("Synthetic:")


def test_the_bakerys_owner_signs_for_every_role() -> None:
    """The bakery-café names no dietitian: its owner holds the three roles (decision B27), so the page offers him
    the dietitian's question too."""
    bakery = shipped_customers()["bakery-cafe"]

    assert set(bakery.people.values()) == {bakery.contact.name}
    assert sorted(bakery.people) == ["dietitian", "finance", "purchasing_manager"]


def test_every_past_order_row_is_labelled_synthetic_where_it_is_shown() -> None:
    """The orders list and the delivery calendar print the label on each row of the route's history, and the orders
    list prints the route's own note under it."""
    assert f'export const SYNTHETIC = "{SYNTHETIC}";' in _read("kitchens.js")
    orders, deliveries = _read("views/orders.js"), _read("views/deliveries.js")
    assert "historyRows().map(" in orders and "${SYNTHETIC}</div></td>" in orders
    assert "${plain(customerNote())}" in orders
    assert "historyRows()" in deliveries and "· ${SYNTHETIC}</span>" in deliveries


# --- what a customer reads about its own rules (the owner's review of /shop, 14 Nov) -------------------------------

RULE_ID_SHOWN = re.compile(r'rule-id|\brule\("[FP]-\d\d"\)|<span class="rule-id[^"]*">[FP]-\d\d')
ALLERGEN_CODE_SHOWN = "<code>${code}</code>"


def test_the_side_card_and_settings_name_no_rule_id_and_no_allergen_code() -> None:
    """Rule ids belong in an order's log and on the developer pages; an allergen is named by its words."""
    for name in ("views/side.js", "views/settings.js"):
        source = _read(name)
        assert RULE_ID_SHOWN.search(source) is None, name
        assert ALLERGEN_CODE_SHOWN not in source, name


def test_the_limits_have_the_same_words_on_the_card_and_in_settings_and_the_card_leads_there() -> None:
    side, settings = _read("views/side.js"), _read("views/settings.js")

    for words in ("Limit per order", "Limit per day"):
        assert words in side and words in settings, words
    assert "#/settings/s-limits" in side and 'id="s-limits"' in settings
    assert "Change in Settings" in side


def test_the_fixed_rules_are_not_listed_to_the_customer() -> None:
    settings = _read("views/settings.js")

    assert "Always, whatever you set" not in settings and "s-fixed" not in settings
    assert "What the agent never does on its own, whatever you set" in settings and 'href="/docs"' in settings
