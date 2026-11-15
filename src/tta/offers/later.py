"""A dated request that nothing meets, offered for the earliest date it can be met (decision B67).

Every product that could fill the request arrives after the date asked for, so the request as asked has no
option. The same products are then offered for their own delivery date, the earliest per request line, in
options that say so: "Delivered Monday 16 Nov, 3 days later than asked". Each line keeps the date that was
asked for in its claims, so its delivery-date claim is ruled out and the option's needed-by check is not met:
rule F-07 sends every such option to a person, who accepts the later date or does not.

Left as they are (ours, decided on 15 Nov 2026):
- a request for confirmed data only: a delivery date that is not met is not a confirmed one, so nothing is
  offered, and the first note names the earliest date and the request to send;
- a request line that stands in for a recipe's ingredient (`RequestLine.stands_in_for`): a stand-in that is
  late as well does not help the dish, and the menu planner must not read it as one that can be had;
- a request of several lines where some arrive in time: its options hold those lines, and a note names the
  earliest date of the others.
No substitute is looked for on the later date: these options hold the request's own products only.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import date, datetime

from tta.offers.candidates import Candidate, Need, exclusion_for
from tta.offers.outcome import LineOutcome

Earliest = tuple[date, tuple[Candidate, ...]]


def earliest_later(need: Need, arrive_later: Sequence[Candidate], now: datetime) -> Earliest | None:
    """The earliest delivery date among the products that are late for the line, and the products that make
    it. A product counts only when it passes every other check with its own date as the needed-by date: one
    with no price, or one that confirmed-only would leave out, is not counted (task FIX-12b)."""
    if need.needed_by is None:
        return None
    fits = [
        (day, candidate)
        for candidate in arrive_later
        if (day := candidate.assessment.available_date) is not None
        and exclusion_for(candidate, replace(need, needed_by=day), now) is None
    ]
    if not fits:
        return None
    earliest = min(day for day, _ in fits)
    return earliest, tuple(candidate for day, candidate in fits if day == earliest)


def later_outcomes(
    outcomes: Sequence[LineOutcome], late: Sequence[Sequence[Candidate]], now: datetime
) -> tuple[LineOutcome, ...]:
    """For a request that has no option: its request lines, each with the products of its earliest later date
    as the ones that fit. Empty when no line has such a date, when a product of the request does arrive in time,
    or when the request is one the module's docstring leaves as it is. The need of each line still names the
    date asked for, so every line built from these outcomes says that its delivery is later."""
    if any(outcome.need.require_confirmed or outcome.fitting for outcome in outcomes):
        return ()  # confirmed data only; or a product does arrive in time, so "nothing can arrive" would be untrue
    found = [
        None if outcome.need.stands_in_for is not None else earliest_later(outcome.need, arrive_later, now)
        for outcome, arrive_later in zip(outcomes, late, strict=True)
    ]
    if not any(found):
        return ()
    return tuple(
        replace(outcome, fitting=each[1] if each is not None else (), excluded=())
        for outcome, each in zip(outcomes, found, strict=True)
    )
