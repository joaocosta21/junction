"""An exclusion with no allergen rule is read as STRICT, and the offer says so (review P4, item M3, decision D2).

Before, such a request was refused with HTTP 422. Valio Aimo, 14 Nov 2026: "if you are not sure you need to flag
it to the user". The safe reading is the strict one. Scores on the 20% "how precisely the agent matches … with the
least manual correction". Hand-built stock over the real catalog.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from tta.contracts.common import AllergenStrictness
from tta.contracts.offer import Offer

NOTE = (
    "Request line 1: no allergen rule was given for milk (AM), so it was read as strict: a product is offered as "
    "safe only when its data states it is free from it."
)
Build = Callable[..., Offer]


def test_an_exclusion_with_no_rule_gives_an_offer_and_says_it_was_read_as_strict(
    build: Build, make_request: Callable[..., Any]
) -> None:
    offer = build([], [], make_request(100, exclude_allergens=("AM",)))

    assert NOTE in offer.notes


def test_an_exclusion_with_a_rule_says_nothing_about_its_reading(
    build: Build, make_request: Callable[..., Any]
) -> None:
    request = make_request(100, exclude_allergens=("AM",), allergen_strictness=AllergenStrictness.DECLARED_ONLY)

    offer = build([], [], request)

    assert not any("read as strict" in note for note in offer.notes)


def test_the_products_are_checked_under_the_strict_rule(
    build: Build, price: Callable[..., Any], stock: Callable[..., Any], make_request: Callable[..., Any]
) -> None:
    """Alpro soya drink 464013 states it is free from milk: it passes, checked under STRICT."""
    request = make_request(10, product_ids=("464013",), exclude_allergens=("AM",))

    offer = build([price("464013", "2.01")], [stock("464013", 100)], request)

    check = offer.options[0].lines[0].allergen_check
    assert check.strictness is AllergenStrictness.STRICT
    assert [finding.strictness for finding in check.findings] == [AllergenStrictness.STRICT]
