"""Sales not made (lane BO): the quantity asked for that confirmed stock did not cover, by product type, with the
reason in Valio Aimo's own data and the value at the offered price; the products that most often matched a request
and could not be confirmed; substitutes offered, confirmed and rejected.

Read from Valio Aimo's view of each offer: the products left out for a requirement of the buyer's are not in it, so
they are neither listed nor counted here (review finding M1).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from decimal import Decimal

from tta.api.insight_models import HowCounted, Missed, MissedProduct, ReasonCount, Shortfall, Substitutes, UnitTotal
from tta.api.insight_steps import ZERO, JsonDict, Order, Step, as_decimal, as_dict, as_list, has_substitute
from tta.audit.phrases import joined, number
from tta.contracts.audit import AuditEventType
from tta.contracts.common import AvailabilityState, OptionKind, OrderStatus, PlacedBy

MAX_TOP_PRODUCTS = 5
# Why a quantity could not be confirmed, where the reason is in Valio Aimo's own data. "Closing time" is the word
# of Valio's own webshop (AIMO/build/replan/P3-webshop.md, the mapping table).
OWN_REASONS = {
    "QUANTITY_NOT_CONFIRMED": "quantity not confirmed in the data",
    "CUTOFF_PASSED": "closing time passed",
    "NOT_DELIVERABLE": "cannot be delivered",
    "OUT_OF_STOCK": "out of stock",
}
UNIT_WORDS = {"L": "L", "KG": "kg", "UNIT": "units"}
FREE_FROM = "FREE_FROM_"
EVERYTHING_COVERED = "Every quantity asked for was covered by confirmed stock of the product asked for."
MISSED_COUNTED = (
    HowCounted(figure="Not confirmed", how="Per requested line of each offer: the quantity asked for minus what "
               "the best confirmed option covers. An offer replaced by an accepted suggestion is counted once, "
               "as the amended offer."),
    HowCounted(figure="Euros", how="The quantity not confirmed at the average net price of what the same offer "
               "did cover. Counted for one-line requests; a line with no offered price has no value."),
    HowCounted(figure="Reasons and products", how="Products that matched a request and were left out for a reason "
               "in Valio Aimo's own data, or offered with a quantity that is not confirmed. Products left out for "
               "a requirement of the buyer's are not shown or counted."),
    HowCounted(figure="Substitutes", how="Offers with a substitute line; orders with one that a person confirmed, "
               "or rejected."),
    HowCounted(figure="Ordered as a substitute", how="For a request that was not fully confirmed: what the "
               "substitute lines of its orders cover, once the order is confirmed by a person or placed by the "
               "agent. It is sold, though not as the product asked for, so it is said beside the quantity not "
               "confirmed and never taken off it. Counted where the request has one line that fell short."),
)


def _claim_words(code: str) -> str:
    """FREE_FROM_LACTOSE -> lactose-free; any other claim in lower case."""
    if code.startswith(FREE_FROM):
        return f"{code.removeprefix(FREE_FROM).lower().replace('_', ' ')}-free"
    return code.lower().replace("_", " ")


def _line_label(line: JsonDict, names: dict[str, str]) -> str:
    """What a requested line asked for, in Valio Aimo's own terms: the product type with its claims, or the
    product by name. Never the buyer's own words, which Valio Aimo's view does not hold."""
    kind = line.get("product_type")
    if isinstance(kind, str) and kind:
        claims = [_claim_words(str(code)) for code in line.get("required_claims") or ()]
        return " ".join([*claims, kind.replace("_", " ")])
    ids = [str(one) for one in line.get("product_ids") or ()]
    if not ids:
        return "a product named in words"
    return f"{names[ids[0]]} ({ids[0]})" if ids[0] in names else f"product {ids[0]}"


class _Short:
    """What one product type, in one unit, was asked for and not confirmed, summed over the offers of the period."""

    def __init__(self) -> None:
        self.asked = self.confirmed = self.missing = self.substituted = ZERO
        self.value: Decimal | None = None
        self.requests = 0
        self.products: defaultdict[str, set[str]] = defaultdict(set)  # reason -> the products it kept out


def _unit_price(offer: JsonDict) -> Decimal | None:
    """The average net price per requested unit of what an offer covers: of its best confirmed option, else of
    the first option that covers anything."""
    options = as_list(offer.get("options"))
    for option in sorted(options, key=lambda one: one.get("kind") != OptionKind.BEST_CONFIRMED):
        covered = sum((as_decimal(part.get("covered")) for part in as_list(option.get("coverage"))), ZERO)
        if covered > ZERO:
            return as_decimal(as_dict(option.get("totals")).get("net")) / covered
    return None


def _coverage(offer: JsonDict, lines: Sequence[JsonDict]) -> list[JsonDict]:
    """What the best confirmed option covers of each requested line; nothing of any line when there is none."""
    best = next((one for one in as_list(offer.get("options")) if one.get("kind") == OptionKind.BEST_CONFIRMED), None)
    if best is not None:
        return as_list(best.get("coverage"))
    return [{"request_line_index": index, "requested": line.get("quantity"), "covered": 0, "unit": line.get("unit"),
             "missing": line.get("quantity")} for index, line in enumerate(lines)]


def _not_confirmed_products(offer: JsonDict) -> dict[str, str | None]:
    """Product id -> name of the lines offered with a quantity that is not confirmed."""
    return {str(line.get("product_id")): line.get("name")
            for option in as_list(offer.get("options")) for line in as_list(option.get("lines"))
            if as_dict(line.get("availability")).get("state") == AvailabilityState.QUANTITY_NOT_CONFIRMED}


def _names(offer: JsonDict) -> dict[str, str]:
    named = [*as_list(offer.get("left_out")), *(line for option in as_list(offer.get("options"))
                                              for line in as_list(option.get("lines")))]
    return {str(one["product_id"]): str(one["name"]) for one in named if one.get("product_id") and one.get("name")}


def missed(steps: Sequence[Step], requests: dict[str, JsonDict], orders: dict[str, Order]) -> Missed:
    replaced = {str(as_dict(step.facts.get("suggestion")).get("offer_id")) for step in steps
                if step.kind == AuditEventType.SUGGESTION_ACCEPTED}
    offers = [as_dict(step.facts.get("offer")) for step in steps
              if step.kind == AuditEventType.OFFER_CREATED and step.offer_id not in replaced]
    shorts: defaultdict[tuple[str, str], _Short] = defaultdict(_Short)
    times: Counter[tuple[str, str]] = Counter()
    names: dict[str, str | None] = {}
    for offer in offers:
        lines = as_list(as_dict(requests.get(str(offer.get("offer_id")))).get("lines"))
        unconfirmed = _not_confirmed_products(offer)
        left_out = [one for one in as_list(offer.get("left_out")) if one.get("reason") in OWN_REASONS]
        for product_id, reason in {*((str(one.get("product_id")), str(one.get("reason"))) for one in left_out),
                                   *((product_id, "QUANTITY_NOT_CONFIRMED") for product_id in unconfirmed)}:
            times[product_id, reason] += 1
        names.update({str(one.get("product_id")): one.get("name") for one in left_out} | unconfirmed)
        short = [part for part in _coverage(offer, lines) if as_decimal(part.get("missing")) > ZERO]
        price = _unit_price(offer) if len(lines) == 1 else None
        for part in short:
            index = part.get("request_line_index")
            line = lines[index] if isinstance(index, int) and 0 <= index < len(lines) else {}
            entry = shorts[_line_label(line, _names(offer)), str(part.get("unit"))]
            entry.requests += 1
            entry.asked += as_decimal(part.get("requested"))
            entry.confirmed += as_decimal(part.get("covered"))
            entry.missing += as_decimal(part.get("missing"))
            if price is not None:
                entry.value = (entry.value or ZERO) + price * as_decimal(part.get("missing"))
            for one in left_out:
                if one.get("request_line_index") == index:
                    entry.products[str(one.get("reason"))].add(str(one.get("product_id")))
            if len(short) == 1:  # an option line does not say which requested line it serves
                entry.products["QUANTITY_NOT_CONFIRMED"].update(unconfirmed)
                entry.substituted += _sold_as_substitute(str(offer.get("offer_id")), orders)
    return _missed_figures(shorts, times, names, offers, orders)


def _sold_as_substitute(offer_id: str, orders: dict[str, Order]) -> Decimal:
    """What the substitute lines of this offer's orders cover, for the orders that were made: confirmed by a
    person or placed by the agent. An order that waits, was rejected or expired sold nothing."""
    made = (order for order in orders.values() if order.offer_id == offer_id and order.status == OrderStatus.ORDERED)
    return sum((order.substitute_covers for order in made), ZERO)


def _shortfall(label: str, unit: str, short: _Short) -> Shortfall:
    word = UNIT_WORDS.get(unit, unit.lower())
    valued = f", about €{short.value:,.0f} at the offered price," if short.value is not None else ""
    instead = ""
    if short.substituted > ZERO:
        verb = "was" if short.substituted == 1 else "were"
        instead = f" {number(short.substituted)} {word} {verb} ordered as a substitute instead."
    sentence = (
        f"{number(short.confirmed)} of {number(short.asked)} {word} of {label} could be confirmed: "
        f"{number(short.missing)} {word}{valued} {'was' if short.missing == 1 else 'were'} not.{instead}"
    )
    reasons = tuple(ReasonCount(reason=reason, label=OWN_REASONS[reason], products=len(short.products[reason]))
                    for reason in OWN_REASONS if short.products.get(reason))
    return Shortfall(label=label, unit=unit, requests=short.requests, asked=short.asked, confirmed=short.confirmed,
                     not_confirmed=short.missing, value_net_eur=short.value,
                     ordered_as_substitute=short.substituted, reasons=reasons, sentence=sentence)


def _missed_figures(
    shorts: dict[tuple[str, str], _Short], times: Counter[tuple[str, str]], names: dict[str, str | None],
    offers: Sequence[JsonDict], orders: dict[str, Order],
) -> Missed:
    rows = sorted((_shortfall(label, unit, short) for (label, unit), short in shorts.items()),
                  key=lambda row: (-(row.value_net_eur or ZERO), -row.not_confirmed, row.label))
    by_unit: defaultdict[str, Decimal] = defaultdict(lambda: ZERO)
    instead: defaultdict[str, Decimal] = defaultdict(lambda: ZERO)
    for row in rows:
        by_unit[row.unit] += row.not_confirmed
        if row.ordered_as_substitute > ZERO:
            instead[row.unit] += row.ordered_as_substitute
    value = sum((row.value_net_eur or ZERO for row in rows), ZERO)
    top = tuple(
        MissedProduct(product_id=product_id, name=names.get(product_id), times=number_of, reason=reason,
                      reason_label=OWN_REASONS[reason])
        for (product_id, reason), number_of in sorted(times.items(), key=lambda one: (-one[1], one[0]))
    )[:MAX_TOP_PRODUCTS]
    with_substitute = [order for order in orders.values() if order.substitute]
    substitutes = Substitutes(
        offered=sum(any(has_substitute(option) for option in as_list(offer.get("options"))) for offer in offers),
        accepted=sum(o.status == OrderStatus.ORDERED and o.placed_by == PlacedBy.HUMAN_APPROVAL
                     for o in with_substitute),
        refused=sum(o.status == OrderStatus.REJECTED for o in with_substitute),
    )
    amounts = joined(f"{number(amount)} {UNIT_WORDS.get(unit, unit.lower())}" for unit, amount in by_unit.items())
    sentence = EVERYTHING_COVERED if not rows else (
        # "Of the product asked for": an offer may also hold an option that fills the quantity from confirmed
        # stock with a substitute, which a person confirms. That is another product; this figure is the product
        # asked for, as the first option of the answer says it.
        f"{amounts} asked for could not be covered by confirmed stock of the product asked for: about "
        f"€{value:,.0f} at offered prices.{_ordered_instead(instead)}"
    )
    return Missed(
        shortfalls=tuple(rows), value_net_eur=value, top_products=top, substitutes=substitutes, sentence=sentence,
        not_confirmed=tuple(UnitTotal(unit=unit, quantity=amount) for unit, amount in by_unit.items()),
        ordered_as_substitute=tuple(UnitTotal(unit=unit, quantity=amount) for unit, amount in instead.items()),
        counted=MISSED_COUNTED,
    )


def _ordered_instead(instead: dict[str, Decimal]) -> str:
    """ " 300 L of that were ordered as a substitute instead." or nothing: said after the quantity not confirmed,
    which it never reduces."""
    if not instead:
        return ""
    amounts = joined(f"{number(amount)} {UNIT_WORDS.get(unit, unit.lower())}" for unit, amount in instead.items())
    verb = "was" if len(instead) == 1 and next(iter(instead.values())) == 1 else "were"
    return f" {amounts} of that {verb} ordered as a substitute instead."
