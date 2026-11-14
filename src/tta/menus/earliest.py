"""The earliest day an ingredient could arrive when it cannot arrive by the day asked (lane FIX-M, review row C3-F6).

Scores on the 15% "robustness to exception situations": "for tomorrow" used to end at "cannot be sourced by Friday";
a kitchen with a last-minute event needs the next day it can have the goods. Nothing is worked out here that the
offer does not already state. Two readings, the offer's own structure first:
1. a product the offer holds for the line that arrives after the day asked (its `availability.available_date`);
2. the offer builder's note for a line with no product ("The earliest delivery date in Valio's data for a product
   that otherwise fits is Monday 16 Nov", `tta.offers.builder`). The offer carries that day in words only, so it is
   read back from the words: the first day after the day asked that is written the same way. When the note is not
   there, or is worded another way, no day is named: nothing is guessed.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date, timedelta

from tta.availability.wording import format_day
from tta.contracts.offer import Offer, OfferLine

# `Request line 2: nothing can arrive by Friday 13 Nov. The earliest delivery date in Valio's data for a product
# that otherwise fits is Monday 16 Nov, for 36 products: ...`
EARLIEST_NOTE = re.compile(
    r"^Request line (?P<line>\d+): .*\bearliest delivery date\b.*? is (?P<day>[A-Z][a-z]+ \d{1,2} [A-Z][a-z]{2})\b"
)
MAX_DAYS_AHEAD = 60  # how far after the day asked a day written in the note is looked for


def arrives_after(lines: Sequence[OfferLine], needed_by: date | None) -> date | None:
    """The day the last of these lines arrives, when that is after the day asked. None: no day was asked, nothing
    is offered, a line states no day, or everything arrives in time."""
    days = [line.availability.available_date for line in lines]
    if needed_by is None or not days or any(day is None for day in days):
        return None
    last = max(days)
    return last if last > needed_by else None


def offered_later(offer: Offer | None, index: int | None, needed_by: date | None) -> date | None:
    """The day the products offered for request line `index` arrive, when that is after the day asked: of the
    first option that holds a product for the line, as the plan's sentence names it (`tta.menus.offered`)."""
    if offer is None or index is None:
        return None
    for option in offer.options:
        lines = [line for line in option.lines if line.request_line_index == index]
        if lines:
            return arrives_after(lines, needed_by)
    return None


def noted_earliest(offer: Offer | None, index: int | None, needed_by: date | None) -> date | None:
    """The earliest delivery day the offer's note names for request line `index`, as a date."""
    if offer is None or index is None or needed_by is None:
        return None
    for note in offer.notes:
        found = EARLIEST_NOTE.match(note)
        if found is not None and int(found["line"]) == index + 1:
            return _day_after(needed_by, found["day"])
    return None


def earliest_date(offer: Offer | None, index: int | None, needed_by: date | None) -> date | None:
    """The earliest day request line `index` could arrive, when it is after the day asked; None when none is known."""
    return offered_later(offer, index, needed_by) or noted_earliest(offer, index, needed_by)


def _day_after(needed_by: date, words: str) -> date | None:
    for ahead in range(1, MAX_DAYS_AHEAD + 1):
        day = needed_by + timedelta(days=ahead)
        if format_day(day) == words:
            return day
    return None
