"""What an offer says when a product's price and stock were recorded later than the rest (lane FC2).

The replay gateway can join recordings (`tta.valio.replay`, task CK): the first one gives the clock, and a
product only a later one holds is answered from it. An offer that holds such a product says so, with both
instants and why reading them together is honest, in the sentence the gateway itself gives
(`join_sentence`). An offer whose products are all of the first recording says nothing: it is unchanged.

The gateway is asked by what it can answer, not by its class: the live client and a test's hand-built gateway
know no recordings and add no note. The sentence is the one a menu plan carries (`tta.menus.sentence`); the
offer package cannot import it from there, because the menus are built on the offers.
"""

from __future__ import annotations

from collections.abc import Sequence

LATER_RECORDED = (
    "{count} of the {total} products of this offer have their price and stock from the later recording "
    "({products}). {join}"
)
MAX_PRODUCTS_NAMED = 12


def later_recorded_note(gateway: object, offered: Sequence[str]) -> str | None:
    """The note for the offered product ids, or None: the gateway joins no recordings, or none of the products
    was answered from a later one."""
    recorded_later = getattr(gateway, "recorded_later", None)
    join = getattr(gateway, "join_sentence", None)
    if recorded_later is None or not join or not offered:
        return None
    later = tuple(recorded_later(offered))
    if not later:
        return None
    named = _joined(later[:MAX_PRODUCTS_NAMED]) + (" and more" if len(later) > MAX_PRODUCTS_NAMED else "")
    return LATER_RECORDED.format(count=len(later), total=len(offered), products=named, join=join)


def _joined(items: Sequence[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"
