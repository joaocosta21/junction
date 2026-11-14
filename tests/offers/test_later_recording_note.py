"""An offer says when a product's price and stock come from a recording made later than the first one (lane
FC2). A menu plan already said it; an offer made outside the planner did not. The recording's own offers are
unchanged: the note is added only when an offered product was recorded later."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from tta.contracts.common import Identity, Unit
from tta.offers import OfferDeps, OfferService
from tta.offers.recorded import later_recorded_note
from tta.valio import ReplayGateway

LATER = "the later recording"


def _offered(offer: Any) -> tuple[str, ...]:
    return tuple(dict.fromkeys(line.product_id for option in offer.options for line in option.lines))


def test_an_offer_of_butter_says_which_products_were_recorded_later(
    service: OfferService, replay: ReplayGateway, make_request: Callable[..., Any], agent_hotel: Identity
) -> None:
    offer = service.build_offer(make_request(10, Unit.KG, product_type="butter"), agent_hotel)

    later = replay.recorded_later(_offered(offer))
    assert later  # the butters were recorded with the baking products, after the demo recording
    note = offer.notes[-1]
    assert note.startswith(
        f"{len(later)} of the {len(_offered(offer))} products of this offer have their price and stock from "
        f"{LATER} ({later[0]}"
    )
    assert replay.join_sentence is not None and note.endswith(replay.join_sentence)
    assert sum(LATER in each for each in offer.notes) == 1


def test_scenario_1s_notes_are_unchanged(
    service: OfferService, replay: ReplayGateway, counting: Any, deps_for: Callable[..., OfferDeps],
    make_request: Callable[..., Any], agent_hotel: Identity,
) -> None:
    offer = service.build_offer(make_request(1000), agent_hotel)
    # The same recording behind a gateway that says nothing about recordings: the notes as they were before.
    plain = OfferService(deps_for(counting(replay))).build_offer(make_request(1000), agent_hotel)

    assert replay.recorded_later(_offered(offer)) == ()
    assert offer.notes == plain.notes
    assert not any(LATER in note for note in offer.notes)


def test_a_gateway_that_knows_no_recordings_adds_nothing(replay: ReplayGateway, counting: Any) -> None:
    assert later_recorded_note(counting(replay), ("464411",)) is None
    assert later_recorded_note(replay, ()) is None
    assert later_recorded_note(replay, ("469363",)) is None  # of the first recording
