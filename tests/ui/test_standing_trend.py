"""The trend on the standing-orders page: what the customer's past orders say, and one renewal at that quantity.

Scores on the 20% "autonomy and controls" (Valio Aimo's scenario: the agent learns a recurring weekly order and
flags a quantity creeping up) and on the 15% "clear visibility of assumptions" (the history is synthetic and the
page says how many past orders each customer file holds). Measured at the recording's own clock.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi.testclient import TestClient

from tta.customers import shipped_customers

CSRF = re.compile(r'name="csrf" value="([A-Za-z0-9_-]+)"')
TREND = "are growing: about 84 L in your last 3 orders, 70 L in the 3 before."
SCHOOL_FORM = re.compile(
    r'<form method="post" action="/standing-orders/so_school_weekly/renew" class="inline-form">(.*?)</form>', re.DOTALL
)
HIDDEN = re.compile(r'<input type="hidden" name="(quantity_\d+)" value="([^"]+)">')


def _csrf(client: TestClient) -> str:
    return CSRF.search(client.get("/standing-orders").text).group(1)  # type: ignore[union-attr]


def _loaded(client: TestClient) -> str:
    loaded = client.post("/standing-orders/demo", data={"csrf": _csrf(client)}, follow_redirects=False)
    assert loaded.status_code == 303
    return client.get("/standing-orders").text


def test_the_page_says_how_many_synthetic_past_orders_each_customer_file_holds(client: TestClient) -> None:
    page = client.get("/standing-orders").text

    assert "six" not in page
    for customer in shipped_customers().values():
        assert f"{customer.name}: {len(customer.history)}" in page  # the banner, from the data
    assert {len(customer.history) for customer in shipped_customers().values()} == {8, 16}


def test_loading_sets_up_every_demo_customers_standing_orders_once(client: TestClient) -> None:
    page = _loaded(client)
    again = _loaded(client)

    for standing_order_id in ("so_demo_hotel_milk", "so_ward_plant_drinks", "so_school_weekly", "so_bakery_weekly"):
        assert page.count(f'<article class="card" id="{standing_order_id}">') == 1
        assert again.count(f'<article class="card" id="{standing_order_id}">') == 1


def test_the_schools_standing_order_shows_the_trend_labelled_synthetic(client: TestClient) -> None:
    page = _loaded(client)

    assert TREND in page and "Your standing order still says 60 L. Renew once at 84 L?" in page
    # One label per button: the sentence now asks "Renew once at 84 L?" itself, so the words are there twice.
    assert page.count("From a synthetic order history</span>") == page.count('<button type="submit">Renew once at') == 1
    assert '<button type="submit">Renew once at 84 L</button>' in page


def test_the_button_renews_once_at_the_suggested_quantity_and_the_renewal_meets_the_rules(
    client: TestClient, own_book: Any
) -> None:
    page = _loaded(client)
    form = next(found for found in SCHOOL_FORM.findall(page) if "Renew once at 84 L" in found)
    quantities = dict(HIDDEN.findall(form))
    assert "84" in quantities.values()

    renewed = client.post("/standing-orders/so_school_weekly/renew",
                          data={"csrf": _csrf(client), **quantities}, follow_redirects=False)

    assert renewed.status_code == 303, renewed.text
    book = own_book(client)
    standing = book.store.get_standing_order("so_school_weekly")
    stored = {line.product_ids[0]: line.quantity for line in standing.request.lines}
    assert stored["470863"] == 60  # one renewal: the stored quantity is a person's to change
    orders = book.store.list_orders(profile_id="school-kitchen")
    assert [order.status.value for order in orders] == ["PENDING_APPROVAL"]  # one renewal, never ordered alone
    assert [line.covers for line in orders[0].option.lines if line.product_id == "470863"] == [84]
    assert "request line 2: 84 L this week against a median of 77 L" in client.get("/standing-orders").text  # P-08
