"""What reading a fact gives: its value, or `Missing` with the reason. Shared by every reader of facts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class Missing:
    """A fact that could not be read, and why. `known` holds the part of a list that is known."""

    reason: str
    known: tuple[str, ...] = ()


FactValue = str | bool | Decimal | datetime | tuple[str, ...]
Reading = FactValue | Missing
