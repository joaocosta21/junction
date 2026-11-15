"""A quantity is written as a plain number everywhere: never `5E+1` for 50.

Found on the running system: a stand-in's `covers` read `5E+1` (hotel, 100 pieces of sodium bicarbonate 465668)
and `1E+1` (school, 10 pieces of Guanaja 462859). Content turned back into pieces is a division, and a Decimal
division can answer with an exponent above zero (25 / 0.5 is `5E+1`); the JSON number hid it and every reader
that writes the Decimal as text showed it. Recording of 14 Nov at the demo clock, read offline.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime
from decimal import Decimal
from typing import Any

import pytest

from tta.config import Settings
from tta.contracts.common import Identity, IdentityKind, Unit
from tta.offers import OfferDeps, OfferService
from tta.offers.stand_ins import _stated
from tta.valio import ReplayGateway

DEMO_CLOCK = datetime.fromisoformat("2026-11-12T14:15:00+02:00")
SODIUM_BICARBONATE, GUANAJA = "465668", "462859"


@pytest.fixture(scope="module")
def demo_service(deps_for: Callable[..., OfferDeps]) -> OfferService:
    return OfferService(deps_for(ReplayGateway(Settings.for_tests().replay_capture_dir, demo_clock=DEMO_CLOCK)))


def _decimals(value: Any, path: str = "offer") -> Iterator[tuple[str, Decimal]]:
    """Every Decimal an offer holds, with where it is."""
    if isinstance(value, Decimal):
        yield path, value
    elif isinstance(value, dict):
        for key, each in value.items():
            yield from _decimals(each, f"{path}.{key}")
    elif isinstance(value, list | tuple):
        for index, each in enumerate(value):
            yield from _decimals(each, f"{path}[{index}]")


@pytest.mark.parametrize(
    ("profile_id", "product_id", "pieces", "stand_in", "covers"),
    [
        ("hotel-kitchen", SODIUM_BICARBONATE, 100, "476713", "50"),  # before: 5E+1
        ("school-kitchen", GUANAJA, 10, "466730", "10"),  # before: 1E+1
    ],
)
def test_what_a_stand_in_covers_is_a_plain_number(
    demo_service: OfferService, make_request: Callable[..., Any], profile_id: str, product_id: str, pieces: int,
    stand_in: str, covers: str,
) -> None:
    identity = Identity(kind=IdentityKind.AGENT, id=f"agent:{profile_id}", display_name="An agent",
                        profile_id=profile_id)

    offer = demo_service.build_offer(make_request(pieces, Unit.UNIT, product_ids=(product_id,)), identity)

    line = next(line for option in offer.options for line in option.lines if line.product_id == stand_in)
    assert str(line.covers) == covers
    written = [(path, str(value)) for path, value in _decimals(offer.model_dump(mode="python"))]
    assert [each for each in written if "E" in each[1]] == []  # no Decimal of the offer is written with an exponent
    assert "E+" not in offer.model_dump_json()


@pytest.mark.parametrize(
    ("covers", "written"),
    [
        (Decimal(25) / Decimal("0.5"), "50"),  # the division answers 5E+1
        (Decimal(25) / Decimal("2.5"), "10"),  # 1E+1
        (Decimal("1E+3"), "1000"),
        (Decimal("19.72727272727272727272727273"), "19.727"),  # cut to three places, rounded down, as before
        (Decimal("12.5"), "12.5"),  # what the step holds stays as it is
        (Decimal("7"), "7"),
    ],
)
def test_covers_is_stated_without_an_exponent(covers: Decimal, written: str) -> None:
    assert str(_stated(covers)) == written
