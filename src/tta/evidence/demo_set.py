"""The demo's products that carry an allergen doubt (AP-3): the list a recording run starts from.

It is measured, not written by hand: every request below is built into an offer in replay, and a product is on
the list when rule P-04 sends it to a person in any option of any of those offers (`products_needing_evidence`).
The requests are each shipped customer's usual products, asked once by type and once by id at the quantity of the
customer's last delivery, plus two named cases: the shop's Elovena example and the almond drink whose declaration
its own ingredient list contradicts (P13 section 2.4).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal

from tta.contracts.common import AllergenStrictness, Unit
from tta.contracts.customer import Customer
from tta.contracts.offer import Offer
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.evidence.finder import products_needing_evidence

DEFAULT_QUANTITY = Decimal(10)  # for a usual product the customer's last delivery did not hold
# (profile, product id, quantity in litres, excluded allergen): asked by id, with the exclusion in the request.
NAMED_CASES: tuple[tuple[str, str, Decimal, str], ...] = (
    ("hotel-kitchen", "469512", Decimal(100), "AM"),  # Elovena barista oat drink, no milk: no statement
    ("hotel-kitchen", "465793", Decimal(10), "AN"),  # Alpro almond drink, no tree nuts: a contradiction
)


def demo_requests(customers: Mapping[str, Customer], needed_by: date) -> tuple[tuple[str, PurchaseRequest], ...]:
    """(profile id, request) for every request of the demo set, in a fixed order."""
    requests: list[tuple[str, PurchaseRequest]] = []
    for profile_id in sorted(customers):
        customer = customers[profile_id]
        last = customer.history[-1].quantities if customer.history else {}
        for usual in customer.usual:
            quantity = Decimal(last.get(usual.product_id, DEFAULT_QUANTITY))
            by_type = RequestLine(text=usual.product_type, product_type=usual.product_type, quantity=quantity,
                                  unit=usual.unit)
            by_id = RequestLine(text=usual.product_id, product_ids=(usual.product_id,), quantity=quantity,
                                unit=usual.unit)
            requests += [(profile_id, PurchaseRequest(needed_by=needed_by, lines=(line,))) for line in (by_type, by_id)]
    for profile_id, product_id, quantity, code in NAMED_CASES:
        line = RequestLine(
            text=product_id, product_ids=(product_id,), quantity=quantity, unit=Unit.L, exclude_allergens=(code,),
            allergen_strictness=AllergenStrictness.STRICT,
        )
        requests.append((profile_id, PurchaseRequest(needed_by=needed_by, lines=(line,))))
    return tuple(requests)


def products_with_doubt(offers: Iterable[Offer]) -> tuple[str, ...]:
    """Every product P-04 sends to a person in any option of the offers, once, sorted by id."""
    found = {
        product_id
        for offer in offers
        for option in offer.options
        for product_id in products_needing_evidence(option, option.decision)
    }
    return tuple(sorted(found))
