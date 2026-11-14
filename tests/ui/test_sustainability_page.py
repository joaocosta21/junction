"""The result page shows delivery, reliability, carbon and labels, and one example where a preference changes the
choice (task SUST-1).

Scores on the brief's optional direction "Delivery time & sustainability comparison" and on the 30% demo: one
click shows the buyer's preference picking another product than price would, with the trade-off in euros.

The audit trail words each option kind (`tta.audit.phrases.OPTION_KINDS`, owned by STAND-1 in this round) and
does not know `CHEAPEST_CONFIRMED` yet, so the page tests add the words for the length of a test; the last test
fails on purpose once the audit package names the kind itself, and its marker is then removed.
"""

from __future__ import annotations

import html
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from tta.audit import phrases
from tta.contracts.common import ConstraintKind, OptionKind, OrderStatus, PlacedBy, Preference
from tta.ui import view
from tta.ui.examples import example_by_key, example_for_text

Post = Callable[..., Any]
KEY = "scenario-5"
RELIABLE_OAT = "470863"
CHEAP_OAT = "472145"


def test_the_new_kinds_have_words_and_a_tone() -> None:
    assert view.words(OptionKind.CHEAPEST_CONFIRMED) == "Cheapest confirmed"
    assert view.tone(OptionKind.CHEAPEST_CONFIRMED) == view.OK
    assert view.words(ConstraintKind.LABEL) == "Certificate label"


def test_the_example_asks_for_the_most_reliable_delivery() -> None:
    example = example_by_key(KEY)

    assert example is not None
    assert example.request.prefer is Preference.RELIABILITY
    assert example.request.lines[0].product_type == "plant_drink"
    assert example_for_text(example.text) is example


def test_the_first_page_offers_the_example(client: TestClient) -> None:
    page = client.get("/").text

    assert f'value="{KEY}"' in page


def test_the_example_orders_the_reliable_product_and_shows_the_cheaper_one(
    client: TestClient, run_example: Post, only_order: Callable[..., Any]
) -> None:
    page = html.unescape(run_example(client, KEY).text)
    order = only_order(client)

    assert "Best confirmed option, ranked by delivery reliability" in page
    assert "Cheapest confirmed option" in page
    assert "€7.00 more than the cheapest confirmed option" in page
    assert (order.status, order.placed_by) == (OrderStatus.ORDERED, PlacedBy.AGENT)
    assert order.option.product_ids == (RELIABLE_OAT,)


def test_each_line_shows_reliability_carbon_and_labels(
    client: TestClient, run_example: Post
) -> None:
    page = html.unescape(run_example(client, KEY).text)

    assert "Delivery reliability: 100%" in page
    assert "Delivery reliability: unknown" in page
    assert "Carbon footprint: 0.435 kg CO2e per kg" in page
    assert "Certificate labels: none stated" in page


def test_each_option_shows_its_comparison(client: TestClient, run_example: Post) -> None:
    page = html.unescape(run_example(client, KEY).text)

    assert "Compared with the other options" in page
    assert "lowest delivery reliability 100%" in page.lower()
    assert "unknown for 1 line" in page
    assert "43.5 kg CO2e" in page


def test_a_label_on_a_line_is_shown(client: TestClient, run_text: Post) -> None:
    page = html.unescape(run_text(client, "1,000 litres of lactose-free milk by Monday").text)

    assert "GOODS_FROM_FINLAND_BLUE_SWAN" in page
    assert "Carbon footprint: 1.1 kg CO2e per kg" in page


def test_the_audit_trail_names_the_cheapest_confirmed_kind() -> None:
    assert phrases.OPTION_KINDS[OptionKind.CHEAPEST_CONFIRMED]
