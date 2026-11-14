"""What the offer holds for one request line of a menu plan, in a sentence (task CK): the product, how many packs,
the price, confirmed stock or "quantity not confirmed", and what is left over when the packs hold more than the
recipe needs. A wholesale pack is often larger than a small menu's need, and the plan says so in numbers.

Scores on the 20% "how precisely the agent matches what the buyer actually asked for": the person sees what the
amount of the recipe becomes as an order before confirming it. Nothing here chooses a product or changes an offer.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from tta.availability.wording import format_amount
from tta.contracts.common import AvailabilityState, Unit
from tta.contracts.offer import Offer, OfferLine, OfferOption
from tta.menus.wording import amount_words, joined

ZERO = Decimal(0)
CONFIRMED = "{amount} sales unit{s} confirmed in stock"
NOT_CONFIRMED = "quantity not confirmed"
OFFERED = "Offered: {lines}."
OPTION_OFFERS = "Option {rank} offers {lines}."
ONE_PACK = " {needed} is needed and the pack holds {pack}, so {left} is left over."
MORE_PACKS = " {needed} is needed and {count} packs hold {delivered}, so {left} is left over."
NOTHING_LEFT = " {needed} is needed and the packs hold exactly that."
TOTAL = "Option {rank}, {title}: {net} before tax, {gross} with tax. {decision}"


def money(value: Decimal) -> str:
    """`€2.57`."""
    return f"€{value:,.2f}"


def _stock_words(line: OfferLine) -> str:
    amount = line.availability.usable_amount
    if line.availability.state is AvailabilityState.CONFIRMED and amount is not None:
        return CONFIRMED.format(amount=format_amount(amount), s="" if amount == 1 else "s")
    if line.availability.state is AvailabilityState.QUANTITY_NOT_CONFIRMED:
        return NOT_CONFIRMED
    return line.availability.state.value.replace("_", " ").lower()


def _line_words(line: OfferLine) -> str:
    return (
        f"{format_amount(line.quantity)} × {line.name} ({line.product_id}) for {money(line.net)} before tax, "
        f"{_stock_words(line)}"
    )


def left_over(lines: Sequence[OfferLine], needed: Decimal, unit: Unit) -> str:
    """What the packs hold beyond the need. Empty when a pack's size is not known in the line's unit: nothing is
    worked out from a size nobody stated."""
    if not lines or any(line.pack_size.value is None or line.pack_size.unit is not unit for line in lines):
        return ""
    delivered = sum((line.quantity * line.pack_size.value for line in lines), ZERO)
    if delivered < needed:
        return ""  # a partial fill: the plan's sentence says the share covered
    words = {"needed": amount_words(needed, unit), "left": amount_words(delivered - needed, unit)}
    if delivered == needed:
        return NOTHING_LEFT.format(**words)
    if len(lines) == 1 and lines[0].quantity == 1:
        return ONE_PACK.format(pack=amount_words(lines[0].pack_size.value, unit), **words)
    count = format_amount(sum((line.quantity for line in lines), ZERO))
    return MORE_PACKS.format(count=count, delivered=amount_words(delivered, unit), **words)


def offered_words(offer: Offer | None, index: int | None, needed: Decimal, unit: Unit) -> str:
    """The sentence for request line `index`: the lines of the first option that holds a product for it. Empty
    when no option does."""
    if offer is None or index is None:
        return ""
    for option in offer.options:
        lines = [line for line in option.lines if line.request_line_index == index]
        if lines:
            said = joined([_line_words(line) for line in lines])
            lead = OFFERED if option.rank == 1 else OPTION_OFFERS
            return lead.format(rank=option.rank, lines=said) + left_over(lines, needed, unit)
    return ""


def total_words(option: OfferOption, said: str | None = None) -> str:
    """One option's total and who must confirm it: `said` when the plan words it (`tta.menus.cover`, an option
    that leaves an ingredient out), else the policy's own sentence."""
    decision = said if said is not None else option.decision.sentence if option.decision is not None else ""
    return TOTAL.format(
        rank=option.rank, title=option.title, net=money(option.totals.net), gross=money(option.totals.gross),
        decision=decision,
    ).strip()
