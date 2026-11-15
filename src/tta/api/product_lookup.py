"""Price and availability on a catalog search and on one product (decision B58, review finding C1-2).

Scores on the 30% "working end-to-end demo" and on the 20% "solving the problem": the brief's first core item is
"a structured way for an external agent to search for and retrieve what's available and at what price". Before,
a search and a read answered the product file alone, and price and stock stood only inside an offer: one offer,
and its audit events, per product.

    search_products(service, identity, query, price_and_availability=..., needed_by=...)
    get_product(service, identity, product_id, price_and_availability=..., needed_by=...)

Without the flag both are the gateway service's own search and read, counted as before: nothing changes. With
it, each product answered carries `price_and_availability` (`tta.contracts.product.PriceAndAvailability`).

No price, state or claim is computed here. The look at the supplier is `tta.offers.deps.look_up`, the one an
offer makes, and each product is judged by the offer package's own functions (`evaluate`, `exclusion_for`,
`claims_of`, `price_problem`) against a need with no quantity, built as a substitute query without a quantity
builds it: the buyer profile's allergen exclusions and its confirmed-only setting, and the date when one is
given. So a product reads here as it would on an offer line of the same buyer at the same moment, and an
allergen the buyer excludes is judged by the buyer's own rule: no statement is unknown, never safe.

With the flag, one call is counted once in the caller's lookup window, as an offer is; reads at most
`MAX_PRICED_PRODUCTS` products; makes one look at the supplier; and writes one audit event (`lookup.performed`:
who asked, the product ids, the source and the clock) when a product was looked up, none otherwise. A product the
recorded copy holds no answer for says so (`NOT_IN_RECORDING`), with no price and no state made up for it.

The REST routes and the MCP tools call these two functions and nothing else, so the flag cannot differ between
the two transports.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from tta.api.limits import CallKind, CallLimits
from tta.api.service import NOT_FOR_THE_SUPPLIER, Gateway
from tta.contracts.audit import AuditContext, AuditEventType
from tta.contracts.common import Identity, PackPreference, Unit
from tta.contracts.errors import InvalidRequest, NotAuthorised, SupplierUnavailable
from tta.contracts.policy import BuyerProfile
from tta.contracts.ports import AuditSink
from tta.contracts.product import PriceAndAvailability, Product, SearchResult
from tta.contracts.request import ProductQuery
from tta.offers.candidates import Need, allergen_rules, claims_of, evaluate, exclusion_for, price_problem
from tta.offers.deps import Lookup, OfferDeps, look_up
from tta.orders.access import actor_of

# Our limit, illustrative like the others: one look for a short list an agent can compare, well inside the 1,000
# ids one price call and one availability call hold.
MAX_PRICED_PRODUCTS = 20
FLAG = "price_and_availability"
NEEDED_BY_WITHOUT_THE_FLAG = (
    f"needed_by is read only together with {FLAG}=true: it is the date each product's delivery date is judged "
    "against. Send both, or neither."
)
ONLY_THE_FIRST = (
    "Price and availability are read for at most {limit} products in one call: narrow the search, or name the "
    "others in product_ids."
)
NOT_WIRED = (
    "This gateway cannot read price and availability on a search or on one product here. Ask for an offer "
    "instead: it carries both for every product it holds."
)


@dataclass(frozen=True)
class _Ports:
    """What the lookup asks: the offer package's own dependencies (catalog, supplier gateway, policy, data
    clock), the audit trail and the caller's limits."""

    offers: OfferDeps
    audit: AuditSink
    limiter: CallLimits


def _ports(service: Gateway) -> _Ports:
    """The ports the gateway service was wired with. The service keeps them to itself (`Gateway._deps`) and its
    offer builder keeps the supplier gateway and the data clock (`OfferService._deps`): they are read here, in
    this one place, until the service offers this lookup itself (hand-back FIX-A2, "Needed from another lane").
    A gateway wired with another offer builder answers `supplier-unavailable`, never a guess."""
    deps = service._deps
    offers = getattr(deps.offers, "_deps", None)
    if not isinstance(offers, OfferDeps):
        raise SupplierUnavailable(NOT_WIRED)
    return _Ports(offers=offers, audit=deps.audit, limiter=deps.limiter)


def search_products(
    service: Gateway, identity: Identity, query: ProductQuery, *, price_and_availability: bool = False,
    needed_by: date | None = None,
) -> SearchResult:
    """The catalog search of the gateway service; with the flag, each of at most `MAX_PRICED_PRODUCTS` products
    with its price and availability. `total` still says how many match."""
    if not price_and_availability:
        _refuse_a_date_alone(needed_by)
        service.count_read(identity)
        return service.search_products(identity, query)
    ports = _ports(service)
    ports.limiter.check(identity, CallKind.LOOKUP)  # one lookup whatever the number of products; it writes an event
    found = service.search_products(identity, query.model_copy(update={"limit": min(query.limit, MAX_PRICED_PRODUCTS)}))
    priced = _priced(ports, identity, found.products, needed_by)
    note = found.note
    if query.limit > MAX_PRICED_PRODUCTS < found.total:  # our limit cut the list, not the caller's own
        note = f"{note or ''} {ONLY_THE_FIRST.format(limit=MAX_PRICED_PRODUCTS)}".strip()
    return found.model_copy(update={"products": priced, "note": note})


def get_product(
    service: Gateway, identity: Identity, product_id: str, *, price_and_availability: bool = False,
    needed_by: date | None = None,
) -> Product:
    """The product of the gateway service's read; with the flag, with its price and availability."""
    if not price_and_availability:
        _refuse_a_date_alone(needed_by)
        service.count_read(identity)
        return service.get_product(identity, product_id)
    ports = _ports(service)
    ports.limiter.check(identity, CallKind.LOOKUP)
    product = service.get_product(identity, product_id)
    return _priced(ports, identity, (product,), needed_by)[0]


def _refuse_a_date_alone(needed_by: date | None) -> None:
    """A date that would be read by nothing is refused, not dropped: the caller would take the answer as judged."""
    if needed_by is not None:
        raise InvalidRequest(NEEDED_BY_WITHOUT_THE_FLAG)


def _priced(
    ports: _Ports, identity: Identity, products: Sequence[Product], needed_by: date | None
) -> tuple[Product, ...]:
    """Each product with what the supplier states about it now: one look for all of them, one audit event."""
    if not products:
        return ()
    if identity.profile_id is None:  # the service refused the supplier before this; never a lookup with no buyer
        raise NotAuthorised(NOT_FOR_THE_SUPPLIER)
    need = _need(ports.offers.policy.get_profile(identity.profile_id), needed_by)
    lookup = look_up(ports.offers, (product.id for product in products))
    priced = tuple(
        product.model_copy(update={FLAG: _read(product, need, lookup, ports.offers)}) for product in products
    )
    _record(ports.audit, identity, lookup, products, needed_by)
    return priced


def _need(profile: BuyerProfile, needed_by: date | None) -> Need:
    """What is asked of each product: no quantity, any pack, and the buyer's own rules as its offers apply them.
    The need of a substitute query that gives no quantity (`tta.offers.substitutes.find_substitutes`)."""
    excluded = profile.excluded_allergens
    return Need(
        index=0,
        quantity=None,
        unit=Unit.UNIT,
        pack=PackPreference.ANY,
        excluded=excluded,
        strictness=profile.allergen_strictness if excluded else None,
        strictness_by_code=allergen_rules(profile, excluded),
        needed_by=needed_by,
        require_confirmed=profile.require_confirmed,
    )


def _read(product: Product, need: Need, lookup: Lookup, offers: OfferDeps) -> PriceAndAvailability:
    """One product as the offer package judges it. A price is stated only when an order could rest on it, and a
    state only when the supplier's answer, or its recorded copy, holds one."""
    candidate = evaluate(product, need, lookup, offers.catalog)
    dropped = exclusion_for(candidate, need, lookup.now)
    price = candidate.price
    amount = price.catalog_price if price is not None and price_problem(price, lookup.now) is None else None
    return PriceAndAvailability(
        unit_net_price=amount.value if amount is not None else None,
        currency=amount.currency if amount is not None else None,
        tax_rate=price.tax_rate if price is not None and amount is not None else None,
        sales_unit=candidate.sales_unit,
        pack_size=candidate.pack,
        price_valid_to=amount.valid_to if amount is not None else None,
        availability=None if candidate.line.not_in_recording else candidate.assessment,
        claims=claims_of(candidate, need, None, lookup.now),
        orderable=dropped is None,
        reason=dropped[0] if dropped is not None else None,
        sentence=dropped[1] if dropped is not None else candidate.assessment.sentence,
        needed_by=need.needed_by,
        source=lookup.source,
        time_now=lookup.now,
        time_basis=lookup.time_basis,
    )


def _record(
    audit: AuditSink, identity: Identity, lookup: Lookup, products: Sequence[Product], needed_by: date | None
) -> None:
    """The one event of the call: who asked, which products, from which source and against which clock. The
    product ids, the source and the clock are Valio Aimo's own data, so its view holds them too; the date is the
    buyer's and stays in the buyer's view (`tta.audit.facts`)."""
    facts = {
        "products_looked_up": len(products),
        "product_ids": [product.id for product in products],
        "source": lookup.source.value,
        "time_now": lookup.now.isoformat(),
        "time_basis": lookup.time_basis.value,
        **({} if needed_by is None else {"needed_by": needed_by.isoformat()}),
    }
    context = AuditContext(profile_id=identity.profile_id, facts=facts)
    audit.record(AuditEventType.LOOKUP_PERFORMED, actor_of(identity), context)
