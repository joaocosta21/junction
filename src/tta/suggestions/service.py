"""The one function the gateway calls: the suggestions to show for an offer, each complete and each checked like
any product (P15 R3).

    found = suggestions_for(customer, request, offer, profile=profile, ports=SuggestionPorts(catalog, gateway, clock))
    found.shown      at most 3, one per kind, in the decided order of kinds, each with price, confirmed stock and
                     `accept_request`
    found.dropped    what the guard did not let through, and Valio Aimo's own suggestion when it stays silent,
                     each with the reason, for the audit trail
    found.held_back  what passed the guard and is not shown, each with the reason a page can show

The decided order of kinds: the forgotten item, the usual product and quantity, a cheaper product with the same
formula, a larger pack, a trend, a new or related product (Valio Aimo's own, last and never more than one).
Decision B32: one per kind and three in all (`ranking`).
Nothing here adds anything to an order: a suggestion carries `accept_request`, a new request for POST /v1/offers,
which meets every rule again and a person's confirmation. No model picks, ranks or words a suggestion.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Iterator, Sequence
from dataclasses import dataclass

from tta.availability import classify
from tta.contracts.common import AvailabilityState, Contract
from tta.contracts.customer import Customer
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.offer import Offer
from tta.contracts.policy import BuyerProfile
from tta.contracts.ports import Catalog, Clock, PairedLookup, ValioGateway
from tta.contracts.request import PurchaseRequest
from tta.contracts.standing import StandingOrder
from tta.contracts.suggestion import Suggestion
from tta.offers.deps import Lookup
from tta.suggestions.alternatives import alternatives, offered_products
from tta.suggestions.companions import forgotten_items
from tta.suggestions.guard import DroppedSuggestion, GuardContext, Proposal, check
from tta.suggestions.history import OrderHistory, history_of
from tta.suggestions.ranking import HeldBackSuggestion, ranked
from tta.suggestions.supplier import related_products, silenced, unknown_type_notes
from tta.suggestions.thresholds import MAX_SUPPLIER_SUGGESTIONS, SUPPLIER_MAX_TRIES
from tta.suggestions.trend import standing_order_trends
from tta.suggestions.usual import usual_products_for_request, usual_quantities_for_request

TWO_SOURCES = "Price and availability came from two sources, so no suggestion was computed on them."
NOT_COMPUTED = "No suggestion was computed: {reason}"


@dataclass(frozen=True)
class SuggestionPorts:
    """What the suggestions read: the product file, price and availability for a few product ids, the clock."""

    catalog: Catalog
    gateway: ValioGateway
    clock: Clock


class SuggestionList(Contract):
    """The answer of `suggestions_for`."""

    shown: tuple[Suggestion, ...] = ()
    dropped: tuple[DroppedSuggestion, ...] = ()
    held_back: tuple[HeldBackSuggestion, ...] = ()  # passed the guard and is not shown, with the reason
    # Why nothing was computed, when the supplier could not be asked; and a product type of the customer file
    # that the catalog does not have.
    notes: tuple[str, ...] = ()


def suggestions_for(
    customer: Customer | None, request: PurchaseRequest, offer: Offer, *, profile: BuyerProfile,
    ports: SuggestionPorts, standing_orders: Sequence[StandingOrder] = (), already_ordered: Collection[str] = (),
    supplier_suggestions: bool = True,
) -> SuggestionList:
    """The suggestions for one offer. `customer`: the buyer's customer file, None for a buyer without one (only the
    catalog kinds then speak). `standing_orders`: the buyer's own, for the trend. `already_ordered`: products in an
    order placed or waiting for the same delivery date. `supplier_suggestions`: False switches Valio Aimo's own off.

    Never raises for a supplier that cannot be reached: the answer then holds no suggestion and says why."""
    try:
        return _suggestions(customer, request, offer, profile, ports, standing_orders, already_ordered,
                            supplier_suggestions)
    except SupplierUnavailable as error:
        return SuggestionList(notes=(NOT_COMPUTED.format(reason=error),))


def _suggestions(
    customer: Customer | None, request: PurchaseRequest, offer: Offer, profile: BuyerProfile,
    ports: SuggestionPorts, standing_orders: Sequence[StandingOrder], already_ordered: Collection[str],
    supplier_suggestions: bool,
) -> SuggestionList:
    catalog = ports.catalog
    offered = offered_products(request, offer, catalog)
    in_request = _in_request(request, offer)
    history = _history(customer, catalog) if customer is not None else None
    proposals = list(_from_history(history, request, offer, profile, standing_orders, in_request))
    proposals += [Proposal(suggestion=each) for each in alternatives(
        customer.customer_id if customer is not None else profile.profile_id, request, offered, profile, catalog,
        lambda ids: look_up(ports, ids),
    )]
    lookup = look_up(ports, (proposal.suggestion.product_id for proposal in proposals))
    context = GuardContext(request=request, profile=profile, lookup=lookup, catalog=catalog,
                           already_ordered=already_ordered)
    checked = [check(proposal, context) for proposal in proposals]
    if supplier_suggestions and customer is not None and history is not None:
        checked += _from_supplier(customer, history, request, in_request, profile, ports, already_ordered)
    found = ranked(each for each in checked if isinstance(each, Suggestion))
    return SuggestionList(
        shown=found.shown, dropped=tuple(each for each in checked if isinstance(each, DroppedSuggestion)),
        held_back=found.held_back, notes=unknown_type_notes(customer) if customer is not None else (),
    )


def look_up(ports: SuggestionPorts, product_ids: Iterable[str]) -> Lookup:
    """One look at price and availability for the ids, both from one source, as an offer is built on
    (`tta.offers.deps.look_up`). No id: no call. Raises `SupplierUnavailable`."""
    ids = tuple(dict.fromkeys(product_ids))
    gateway = ports.gateway
    if not ids:
        return Lookup(prices={}, availability={}, now=ports.clock.now(), source=gateway.source,
                      basis=getattr(gateway, "time_basis", None))
    if isinstance(gateway, PairedLookup):
        prices, availability = gateway.look_up(ids)
    else:
        prices, availability = gateway.price(ids), gateway.availability(ids)
    if prices.source is not availability.source:
        raise SupplierUnavailable(TWO_SOURCES)
    return Lookup(prices=prices.by_id(), availability=availability.by_id(), now=availability.time_now,
                  source=availability.source, basis=availability.basis)


def _history(customer: Customer, catalog: Catalog) -> OrderHistory:
    """The customer's history, with each usual product's name from the catalog for the sentences."""
    products = {usual.product_id: catalog.get_product(usual.product_id) for usual in customer.usual}
    names = {product_id: product.display_name for product_id, product in products.items() if product is not None}
    return history_of(customer, names)


def _in_request(request: PurchaseRequest, offer: Offer) -> tuple[str, ...]:
    """The products the request names and the products the first option chose, each once."""
    named = [product_id for line in request.lines for product_id in line.product_ids]
    chosen = [line.product_id for line in offer.options[0].lines] if offer.options else []
    return tuple(dict.fromkeys([*named, *chosen]))


def _chosen_for_type_only_lines(request: PurchaseRequest, offer: Offer) -> tuple[str, ...]:
    """What the first option chose for the lines that name a type and no product: the forgotten item starts
    from them, since such a line has no product of its own."""
    if not offer.options:
        return ()
    return tuple(dict.fromkeys(
        line.product_id for line in offer.options[0].lines
        if line.request_line_index < len(request.lines) and not request.lines[line.request_line_index].product_ids
    ))


def _chosen_for_line(offer: Offer, index: int | None) -> tuple[str, ...]:
    if not offer.options:
        return ()
    return tuple(line.product_id for line in offer.options[0].lines if line.request_line_index == index)


def _from_history(history: OrderHistory | None, request: PurchaseRequest, offer: Offer, profile: BuyerProfile,
                  standing_orders: Sequence[StandingOrder], in_request: Collection[str]) -> Iterator[Proposal]:
    if history is None:
        return
    chosen = _chosen_for_type_only_lines(request, offer)
    for forgotten in forgotten_items(history, request, offered_product_ids=chosen):
        yield Proposal(suggestion=forgotten)
    for usual in usual_products_for_request(history, request):
        if _chosen_for_line(offer, usual.request_line_index) != (usual.product_id,):
            yield Proposal(suggestion=usual)  # silent when the offer already chose the usual product alone
    if request.standing_order_id is None:  # a renewal's quantity is rule P-08's to judge
        for quantity in usual_quantities_for_request(history, request):
            yield Proposal(suggestion=quantity)
    for standing in standing_orders:
        for trend in standing_order_trends(history, standing, tolerance=profile.standing_order_drift_ratio):
            if request.standing_order_id == standing.standing_order_id or trend.product_id in in_request:
                yield Proposal(suggestion=trend)


def _from_supplier(customer: Customer, history: OrderHistory, request: PurchaseRequest,
                   in_request: Collection[str], profile: BuyerProfile, ports: SuggestionPorts,
                   already_ordered: Collection[str]) -> list[Suggestion | DroppedSuggestion]:
    """Valio Aimo's related products through the same guard, best first, until `MAX_SUPPLIER_SUGGESTIONS` pass.
    Price and stock are asked once for the whole pool; only products with confirmed stock are put to the guard,
    at most `SUPPLIER_MAX_TRIES` of them, so the log holds a few drops and not the catalog. One that passes and
    stays silent (decision B32, `supplier.silenced`) is a drop like the others, and the next one is tried."""
    pool = related_products(customer, history, request, in_request, ports.catalog)
    if not pool:
        return []
    lookup = look_up(ports, (each.suggestion.product_id for each in pool))
    context = GuardContext(request=request, profile=profile, lookup=lookup, catalog=ports.catalog,
                           already_ordered=already_ordered)
    in_stock = [each for each in pool
                if classify(lookup.line(each.suggestion.product_id), lookup.now).state is AvailabilityState.CONFIRMED]
    checked: list[Suggestion | DroppedSuggestion] = []
    passed = 0
    for each in in_stock[:SUPPLIER_MAX_TRIES]:
        result = check(Proposal(suggestion=each.suggestion, like_product_id=each.anchor_id), context)
        if isinstance(result, Suggestion):
            result = silenced(each, result) or result
        checked.append(result)
        passed += isinstance(result, Suggestion)
        if passed >= MAX_SUPPLIER_SUGGESTIONS:
            break
    return checked
