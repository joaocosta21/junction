"""Valio Aimo's own suggestion: a related product the customer has never ordered (P15 R11, kind FROM_SUPPLIER).

The brief's example, verbatim: "Proactive selling agent: Valio Aimo's own agent spots a new or seasonal product and
proactively suggests it to the buyer's agent." It comes from the supplier's side, not from the buyer's history, so
it says so: `serves: SUPPLIER`, `evidence.source: SUPPLIER`, the sentence starts "Valio Aimo suggests", and it is
the last kind and never more than one.

What it rests on. The product file has no "new" and no "seasonal" mark: of its fields only
`synkkaData.lastUpdated` is a date, and it says when the data record changed, not when the product was launched
(checked over the 17,546 products on 14 Nov 2026). So this is "related", from catalog facts anyone can check: a
product of the same product type and the same brand as one the customer usually orders, that is in none of the
customer's past orders and not in this request. Ranked by facts of the product file only: the anchor the request
asks for first, then the same kind of pack (bulk or portions), the same flavour and the same use as the anchor,
then a certificate label the anchor does not carry.
It is a proposal like any other: the guard checks it, and accepting posts a new request. One that passes still
stays silent (decision B32) when it is another pack kind than the usual product it resembles (a portion milk for
a school's bulk milk) or when one sales unit is confirmed in stock: it is dropped with the reason, for the
buyer's log only.
"""

from __future__ import annotations

from collections.abc import Collection, Iterator, Sequence
from dataclasses import dataclass
from decimal import Decimal

from tta.catalog.kinds import flavours_of, is_other_use, is_product_type, uses_of
from tta.contracts.common import Unit
from tta.contracts.customer import Customer, UsualProduct
from tta.contracts.ports import Catalog
from tta.contracts.product import Product
from tta.contracts.request import MAX_REQUEST_LINES, ProductQuery, PurchaseRequest, RequestLine
from tta.contracts.suggestion import (
    EvidenceSource,
    Serves,
    Suggestion,
    SuggestionEvidence,
    SuggestionKind,
    suggestion_id_for,
)
from tta.offers.wording import plain_name
from tta.suggestions.guard import DroppedSuggestion, DropReason, Failure, dropped
from tta.suggestions.history import OrderHistory
from tta.suggestions.requests import with_line_added
from tta.suggestions.thresholds import ALTERNATIVES_MAX_POOL, SUPPLIER_MAX_POOL, SUPPLIER_MIN_CONFIRMED_UNITS
from tta.suggestions.wording import number, sentence, type_words

ONE_SALES_UNIT = Decimal(1)  # rounded up to the lot: the smallest whole quantity a kitchen can try
NOT_FROM_YOUR_ORDERS = "Suggested by Valio Aimo from its catalog, not from your orders."
STAYS_SILENT = "Valio Aimo's own suggestion stays silent: "


@dataclass(frozen=True)
class Related:
    """A product related to one the customer usually orders, before price, stock and the guard."""

    suggestion: Suggestion
    anchor_id: str  # the usual product it is related to: the guard holds it to that product's dietary claims
    anchor_label: str = ""  # "Arla Milkdrink 1L lactose free fat free UHT Suomesta (462775)", for the log
    anchor_type: str = ""  # the usual product's type: "milk"
    portion_pack: bool = False  # the product is a pack of portions
    other_pack: bool = False  # a portion pack for a usual product that is not one, or the other way round


def silenced(related: Related, passed: Suggestion) -> DroppedSuggestion | None:
    """Why a related product that passed the guard is still not Valio Aimo's suggestion (decision B32); None
    when it may be shown."""
    if related.other_pack:
        return dropped(passed, _other_pack(related))
    usable = passed.availability.usable_amount if passed.availability is not None else None
    if usable is not None and usable < SUPPLIER_MIN_CONFIRMED_UNITS:
        units = f"{number(usable)} sales unit{'' if usable == 1 else 's'}"
        said = f"{STAYS_SILENT}{units} of {passed.name} ({passed.product_id}) {'is' if usable == 1 else 'are'} " \
               "confirmed in stock."
        summary = f"only {units} {'is' if usable == 1 else 'are'} confirmed in stock"
        return dropped(passed, Failure(DropReason.ONE_UNIT_IN_STOCK.value, said, summary))
    return None


def _other_pack(related: Related) -> Failure:
    product = f"{related.suggestion.name} ({related.suggestion.product_id})"
    kind = type_words(related.anchor_type)
    if related.portion_pack:
        said = f"{product} is a portion pack, and the {related.anchor_label} you usually order is not."
        summary = f"it is a portion pack and your usual {kind} is not"
    else:
        said = f"{product} is not a portion pack, and the {related.anchor_label} you usually order is one."
        summary = f"it is not a portion pack and your usual {kind} is one"
    return Failure(DropReason.OTHER_PACK_KIND.value, f"{STAYS_SILENT}{said}", summary)


def related_products(customer: Customer, history: OrderHistory, request: PurchaseRequest,
                     in_request: Collection[str], catalog: Catalog) -> tuple[Related, ...]:
    """The related products Valio Aimo could put forward, best first, at most `SUPPLIER_MAX_POOL`. `in_request`:
    the products the request names or the offer chose."""
    if len(request.lines) >= MAX_REQUEST_LINES:
        return ()  # accepting would need one more line than a request may hold
    known = {usual.product_id for usual in customer.usual} | set(in_request)
    known |= {product_id for order in history.orders for product_id in order.quantities}
    ranked = sorted(_candidates(customer, history, in_request, known, catalog), key=lambda item: item[0])
    seen: dict[str, Related] = {}
    for _, anchor, product, label in ranked:
        if product.id not in seen:
            seen[product.id] = _related(customer, history, request, anchor, product, label, catalog)
    return tuple(seen.values())[:SUPPLIER_MAX_POOL]


def _pack_kinds(product: Product, anchor_id: str, catalog: Catalog) -> tuple[bool, bool]:
    """(the product is a portion pack, it is another pack kind than the anchor)."""
    anchor = catalog.get_product(anchor_id)
    portion = catalog.is_portion_pack(product)
    return portion, anchor is not None and catalog.is_portion_pack(anchor) is not portion


def _candidates(customer: Customer, history: OrderHistory, in_request: Collection[str], known: Collection[str],
                catalog: Catalog) -> Iterator[tuple[tuple[object, ...], UsualProduct, Product, str | None]]:
    for position, usual in enumerate(_anchors(customer, history, in_request)):
        anchor = catalog.get_product(usual.product_id)
        if anchor is None or not anchor.brand:
            continue  # a brand that is not stated is never read as the same brand
        for product in _same_type(usual.product_type, catalog):
            if product.id in known or product.brand != anchor.brand:
                continue
            gained = next((label for label in product.labels if label not in anchor.labels), None)
            other_flavour = flavours_of(product) != flavours_of(anchor)
            other_use = is_other_use(uses_of(anchor), uses_of(product))
            other_pack = catalog.is_portion_pack(product) is not catalog.is_portion_pack(anchor)
            key = (position, other_pack, other_flavour, other_use, gained is None, product.id)
            yield key, usual, product, gained


def _anchors(customer: Customer, history: OrderHistory, in_request: Collection[str]) -> Sequence[UsualProduct]:
    """The usual products the customer has ordered: those of this request first, then the most ordered."""
    ordered = [usual for usual in customer.usual if history.orders_with(usual.product_id)]
    return sorted(ordered, key=lambda usual: (usual.product_id not in in_request,
                                              -len(history.orders_with(usual.product_id))))


def _same_type(product_type: str, catalog: Catalog) -> tuple[Product, ...]:
    if not is_product_type(product_type):
        return ()  # nothing is related through it, and `unknown_type_notes` says so on the suggestion list
    found = catalog.search(ProductQuery(product_type=product_type, limit=ALTERNATIVES_MAX_POOL))
    return tuple(product for product in found.products if not product.deleted)


def unknown_type_notes(customer: Customer) -> tuple[str, ...]:
    """One sentence when the customer file names a product type the catalog does not have (review finding
    S15). The loader refuses such a file (`tta.customers.loader`); a customer built another way still says it
    here instead of a silent "no related product"."""
    unknown = {
        usual.product_type: usual.product_id for usual in reversed(customer.usual)
        if not is_product_type(usual.product_type)
    }
    if not unknown:
        return ()
    named = ", ".join(f"{plain_name(key)} (for {product_id})" for key, product_id in reversed(unknown.items()))
    return (
        f"The customer file names a product type the catalog does not have: {named}. No related product could "
        "be suggested from it.",
    )


def _related(customer: Customer, history: OrderHistory, request: PurchaseRequest, usual: UsualProduct,
             product: Product, label: str | None, catalog: Catalog) -> Related:
    quantity = catalog.round_to_lot(product, ONE_SALES_UNIT)
    name, kind = product.display_name, type_words(usual.product_type)
    orders = len(history.orders)
    past = f"your {orders} past orders{' (a synthetic history)' if history.synthetic else ''}"
    said = sentence(
        f"Valio Aimo suggests {name} ({product.id}): a {kind} of the brand {product.brand}, like the "
        f"{history.label(usual.product_id)} you usually order, and in none of {past}.",
        f"It carries the label {label}, which your usual product does not." if label else "",
        NOT_FROM_YOUR_ORDERS,
    )
    line = RequestLine(text=f"{name}, suggested by Valio Aimo", product_ids=(product.id,), quantity=quantity,
                       unit=Unit.UNIT)
    evidence = SuggestionEvidence(
        source=EvidenceSource.SUPPLIER, synthetic=history.synthetic, orders_considered=orders, orders_matching=0,
        first_order=history.orders[0].delivered_on if history.orders else None,
        last_order=history.orders[-1].delivered_on if history.orders else None,
    )
    suggestion = Suggestion(
        suggestion_id=suggestion_id_for(customer.customer_id, SuggestionKind.FROM_SUPPLIER, product.id),
        kind=SuggestionKind.FROM_SUPPLIER, serves=Serves.SUPPLIER, customer_id=customer.customer_id,
        product_id=product.id, name=name, quantity=quantity, unit=Unit.UNIT, sentence=said, evidence=evidence,
        accept_request=with_line_added(request, line),
    )
    portion, other_pack = _pack_kinds(product, usual.product_id, catalog)
    return Related(suggestion=suggestion, anchor_id=usual.product_id, anchor_label=history.label(usual.product_id),
                   anchor_type=usual.product_type, portion_pack=portion, other_pack=other_pack)
