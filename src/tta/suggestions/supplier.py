"""Valio Aimo's own suggestion: a product of the same kind as one the customer buys, shown only with a benefit it can
state (P15 R11, kind FROM_SUPPLIER; the owner's rule of 14 Nov 2026).

The brief's example, verbatim: "Proactive selling agent: Valio Aimo's own agent spots a new or seasonal product and
proactively suggests it to the buyer's agent." It comes from the supplier's side, not from the buyer's history, so
it says so: `serves: SUPPLIER`, `evidence.source: SUPPLIER`, the sentence ends "Suggested by Valio Aimo, not from
your orders.", and it is the last kind and never more than one.

What it rests on. The product file has no "new" and no "seasonal" mark: of its fields only
`synkkaData.lastUpdated` is a date, and it says when the data record changed, not when the product was launched
(checked over the 17,546 products on 14 Nov 2026). So a candidate is a product of the same brand and the same kind
as a usual product the customer has ordered: the same product types (`product_types_of`), the same use (`uses_of`:
cooking for cooking, whipping for whipping, coffee for coffee; a name that states no use only for another with
none) and the same flavours (`flavours_of`: plain for plain). It is in none of the customer's past orders, not in
this request, and not already put forward by another kind of suggestion.

It takes the place of that usual product: the quantity is the customer's usual quantity of it (the median of its
last orders), or the quantity of the request line that names it, which accepting changes to the candidate. It is
shown only with a benefit computed from the data in front of it (`supplier_benefits`), and it goes through the
guard like any product (`guard.check`, with the usual product as the one it replaces: no allergen added, the
formula kept where the profile says it matters). One that passes still stays silent (decision B32) when it is
another pack kind than the usual product, when one sales unit is confirmed in stock, or when it has no benefit to
state: it is dropped with the reason, for the buyer's log only.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterable, Iterator, Sequence
from dataclasses import dataclass
from decimal import Decimal

from tta.availability import classify
from tta.catalog.kinds import flavours_of, is_product_type, product_types_of, uses_of
from tta.contracts.common import AvailabilityState
from tta.contracts.customer import Customer, UsualProduct
from tta.contracts.policy import BuyerProfile
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
from tta.offers.deps import Lookup
from tta.offers.wording import plain_name
from tta.suggestions.guard import DroppedSuggestion, DropReason, Failure, GuardContext, Proposal, check, dropped
from tta.suggestions.history import OrderHistory
from tta.suggestions.requests import with_line_added, with_line_changed
from tta.suggestions.supplier_benefits import Benefit, stated_benefits, strength
from tta.suggestions.thresholds import (
    ALTERNATIVES_MAX_POOL,
    MAX_SUPPLIER_SUGGESTIONS,
    SUPPLIER_MAX_POOL,
    SUPPLIER_MAX_TRIES,
    SUPPLIER_MIN_CONFIRMED_UNITS,
    USUAL_QUANTITY_WINDOW,
)
from tta.suggestions.wording import amount, middle, number, short_label, type_words

LookUp = Callable[[Iterable[str]], Lookup]
NOT_FROM_YOUR_ORDERS = "Suggested by Valio Aimo, not from your orders."
STAYS_SILENT = "Valio Aimo's own suggestion stays silent: "
NOTHING_TO_SUGGEST = "Valio Aimo had nothing to suggest that offers a stated benefit: "
NO_BENEFIT = "it offers no benefit Valio Aimo can state"


@dataclass(frozen=True)
class Related:
    """A product of the same kind as one the customer usually orders, before price, stock and the guard."""

    suggestion: Suggestion  # its quantity, the request accepting posts, the usual product it takes the place of
    anchor_id: str  # the usual product it is related to: the guard holds it to that product's claims
    anchor_label: str = ""  # "Arla Milkdrink (462775)", for the sentences
    anchor_type: str = ""  # the usual product's type: "milk"
    portion_pack: bool = False  # the product is a pack of portions
    other_pack: bool = False  # a portion pack for a usual product that is not one, or the other way round
    in_request: bool = False  # a line of the request names the usual product: accepting changes that line

    @property
    def quantity_words(self) -> str:
        """ "your usual 10 L", or "your 100 L" for the quantity of the request line."""
        said = amount(self.suggestion.quantity, self.suggestion.unit)
        return f"your {said}" if self.in_request else f"your usual {said}"


def supplier_suggestion(customer: Customer, history: OrderHistory, request: PurchaseRequest,
                        in_request: Collection[str], *, taken: Collection[str], profile: BuyerProfile,
                        catalog: Catalog, look_up: LookUp,
                        already_ordered: Collection[str] = ()) -> list[Suggestion | DroppedSuggestion]:
    """Valio Aimo's own suggestion, at most one, and the related products dropped on the way, each with its reason.
    Price and stock are asked once for the pool and the usual products it relates to; the products with confirmed
    stock are put to the guard strongest benefit first, at most `SUPPLIER_MAX_TRIES` of them, so the log holds a
    few drops and not the catalog. `taken`: products another kind of suggestion already puts forward."""
    pool = related_products(customer, history, request, in_request, catalog, taken=taken)
    if not pool:
        return []
    lookup = look_up([*(each.suggestion.product_id for each in pool), *(each.anchor_id for each in pool)])
    context = GuardContext(request=request, profile=profile, lookup=lookup, catalog=catalog,
                           already_ordered=already_ordered)
    confirmed = [each for each in pool if classify(lookup.line(each.suggestion.product_id), lookup.now).state
                 is AvailabilityState.CONFIRMED]
    ranked = sorted((_stated(each, request, profile, lookup, catalog) for each in confirmed),
                    key=lambda each: (each.related.other_pack, strength(each.benefits)))
    checked: list[Suggestion | DroppedSuggestion] = []
    for each in ranked[:SUPPLIER_MAX_TRIES]:
        if each.related.other_pack:  # another pack kind is never the same kind of thing: silent, not judged
            checked.append(dropped(each.suggestion, _other_pack(each.related)))
            continue
        result = check(Proposal(suggestion=each.suggestion, like_product_id=each.related.anchor_id), context)
        if isinstance(result, Suggestion):
            result = silenced(each.related, result) or (result if each.benefits else no_benefit(each.related, result))
        checked.append(result)
        if sum(isinstance(one, Suggestion) for one in checked) >= MAX_SUPPLIER_SUGGESTIONS:
            break
    return checked


@dataclass(frozen=True)
class Stated:
    """A related product, its suggestion worded with its strongest benefit, and every benefit found."""

    related: Related
    suggestion: Suggestion
    benefits: tuple[Benefit, ...] = ()


def _stated(related: Related, request: PurchaseRequest, profile: BuyerProfile, lookup: Lookup,
            catalog: Catalog) -> Stated:
    suggestion, found = stated_benefits(related.suggestion, related.anchor_id, related.anchor_type,
                                        related.quantity_words, request=request, profile=profile, lookup=lookup,
                                        catalog=catalog, closing=NOT_FROM_YOUR_ORDERS)
    return Stated(related=related, suggestion=suggestion, benefits=found)


def silenced(related: Related, passed: Suggestion) -> DroppedSuggestion | None:
    """Why a related product that passed the guard is still not Valio Aimo's suggestion (decision B32); None
    when it may be shown."""
    if related.other_pack:
        return dropped(passed, _other_pack(related))
    usable = passed.availability.usable_amount if passed.availability is not None else None
    if usable is not None and usable < SUPPLIER_MIN_CONFIRMED_UNITS:
        units = f"{number(usable)} pack{'' if usable == 1 else 's'}"
        label = short_label(passed.name, passed.product_id)
        said = f"{STAYS_SILENT}{units} of {label} {'is' if usable == 1 else 'are'} confirmed in stock."
        summary = f"only {units} {'is' if usable == 1 else 'are'} confirmed in stock"
        return dropped(passed, Failure(DropReason.ONE_UNIT_IN_STOCK.value, said, summary))
    return None


def no_benefit(related: Related, passed: Suggestion) -> DroppedSuggestion:
    """A related product that passed every check and has no benefit to state: silent, for the buyer's log."""
    said = (f"{NOTHING_TO_SUGGEST}{short_label(passed.name, passed.product_id)} passed every check, and the data "
            f"shows no lower price for the same formula, no stock where your {related.anchor_label} is short, no "
            f"claim or label yours lacks and no fewer packs for {related.quantity_words}.")
    return dropped(passed, Failure(DropReason.NO_STATED_BENEFIT.value, said, NO_BENEFIT))


def _other_pack(related: Related) -> Failure:
    product = short_label(related.suggestion.name, related.suggestion.product_id)
    kind = type_words(related.anchor_type)
    if related.portion_pack:
        said = f"{product} is a portion pack, and the {related.anchor_label} you usually order is not."
        summary = f"it is a portion pack and your usual {kind} is not"
    else:
        said = f"{product} is not a portion pack, and the {related.anchor_label} you usually order is one."
        summary = f"it is not a portion pack and your usual {kind} is one"
    return Failure(DropReason.OTHER_PACK_KIND.value, f"{STAYS_SILENT}{said}", summary)


def related_products(customer: Customer, history: OrderHistory, request: PurchaseRequest,
                     in_request: Collection[str], catalog: Catalog, *,
                     taken: Collection[str] = ()) -> tuple[Related, ...]:
    """The products Valio Aimo could put forward, best first, at most `SUPPLIER_MAX_POOL`. `in_request`: the
    products the request names or the offer chose; `taken`: those another kind of suggestion puts forward."""
    if len(request.lines) >= MAX_REQUEST_LINES:
        return ()  # accepting may need one more line than a request may hold
    known = {usual.product_id for usual in customer.usual} | set(in_request) | set(taken)
    known |= {product_id for order in history.orders for product_id in order.quantities}
    ranked = sorted(_candidates(customer, history, in_request, known, catalog), key=lambda item: item[0])
    seen: dict[str, Related] = {}
    for _, usual, anchor, product in ranked:
        if product.id not in seen:
            seen[product.id] = _related(customer, history, request, usual, anchor, product, catalog)
    return tuple(seen.values())[:SUPPLIER_MAX_POOL]


def _kind_of(product: Product) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """What "the same kind" compares: the product types, the uses and the flavours its data and names give."""
    return product_types_of(product), uses_of(product), flavours_of(product)


def _candidates(customer: Customer, history: OrderHistory, in_request: Collection[str], known: Collection[str],
                catalog: Catalog) -> Iterator[tuple[tuple[object, ...], UsualProduct, Product, Product]]:
    for position, usual in enumerate(_anchors(customer, history, in_request)):
        anchor = catalog.get_product(usual.product_id)
        if anchor is None or not anchor.brand:
            continue  # a brand that is not stated is never read as the same brand
        kind = _kind_of(anchor)
        for product in _same_type(usual.product_type, catalog):
            if product.id in known or product.brand != anchor.brand or _kind_of(product) != kind:
                continue  # a cooking-cream buyer is never offered a whipping cream
            other_pack = catalog.is_portion_pack(product) is not catalog.is_portion_pack(anchor)
            yield (position, other_pack, product.id), usual, anchor, product


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


def _usual_quantity(history: OrderHistory, usual: UsualProduct) -> Decimal:
    """The median of the usual product's last orders: the quantity a real order of it holds."""
    values = [order.quantities[usual.product_id] for order in history.orders_with(usual.product_id)]
    return middle(values[-USUAL_QUANTITY_WINDOW:])


def _related(customer: Customer, history: OrderHistory, request: PurchaseRequest, usual: UsualProduct,
             anchor: Product, product: Product, catalog: Catalog) -> Related:
    holding = next((index for index, line in enumerate(request.lines) if line.product_ids == (anchor.id,)), None)
    if holding is not None:
        quantity, unit = request.lines[holding].quantity, request.lines[holding].unit
    else:
        quantity, unit = _usual_quantity(history, usual), usual.unit
    name, anchor_label = product.display_name, short_label(anchor.display_name, anchor.id)
    text = f"{name}, suggested by Valio Aimo in place of {anchor.id}"
    if holding is not None:
        accept = with_line_changed(request, holding, text=text, product_ids=[product.id])
    else:
        accept = with_line_added(request, RequestLine(text=text, product_ids=(product.id,), quantity=quantity,
                                                      unit=unit))
    evidence = SuggestionEvidence(
        source=EvidenceSource.SUPPLIER, synthetic=history.synthetic, orders_considered=len(history.orders),
        orders_matching=0, first_order=history.orders[0].delivered_on if history.orders else None,
        last_order=history.orders[-1].delivered_on if history.orders else None,
    )
    suggestion = Suggestion(
        suggestion_id=suggestion_id_for(customer.customer_id, SuggestionKind.FROM_SUPPLIER, product.id),
        kind=SuggestionKind.FROM_SUPPLIER, serves=Serves.SUPPLIER, customer_id=customer.customer_id,
        request_line_index=holding, product_id=product.id, name=name, quantity=quantity, unit=unit,
        replaces_product_id=anchor.id, evidence=evidence, accept_request=accept,
        sentence=f"Valio Aimo suggests {short_label(name, product.id)} in place of {anchor_label}. "
                 f"{NOT_FROM_YOUR_ORDERS}",
    )
    portion = catalog.is_portion_pack(product)
    return Related(suggestion=suggestion, anchor_id=anchor.id, anchor_label=anchor_label,
                   anchor_type=usual.product_type, portion_pack=portion,
                   other_pack=portion is not catalog.is_portion_pack(anchor), in_request=holding is not None)
