"""One request line after every candidate was judged: what the planner works from (SPEC section 5, step 2)."""

from __future__ import annotations

from dataclasses import dataclass

from tta.contracts.offer import Exclusion
from tta.contracts.request import RequestLine
from tta.offers.candidates import Candidate, Need


@dataclass(frozen=True)
class LineOutcome:
    """One request line after every candidate was judged."""

    need: Need
    asked: RequestLine
    considered: int
    fitting: tuple[Candidate, ...]  # passed every exclusion check; state CONFIRMED or QUANTITY_NOT_CONFIRMED
    excluded: tuple[Exclusion, ...]
