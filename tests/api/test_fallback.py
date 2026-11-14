"""Live mode with a fall-back to the replay capture (SPEC section 10, tasks T09 and FIX-8).

Scores on the 30% "working end-to-end demo": the flow survives the mock API being down or the call budget
being spent. One look at price and availability comes from one source, and every answer says which.
The same through the application: `test_live_mode.py`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from tta.api.fallback import LIVE_CALLS_PER_LOOK, MIN_CALLS_REMAINING, RETRY_LIVE_AFTER_SECONDS, FallbackGateway
from tta.api.limits import MAX_LIVE_LOOKS_PER_MINUTE
from tta.contracts.availability import PriceResponse
from tta.contracts.common import DataSource
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.ports import PairedLookup, ValioGateway
from tta.valio import ReplayGateway

IDS = ("464013", "469363")
PRICE, AVAILABILITY = "price", "availability"
FakeLive = Any  # the stand-in for the live client, from conftest.py


class FakeTime:
    def __init__(self) -> None:
        self.seconds = 500.0

    def __call__(self) -> float:
        return self.seconds


@pytest.fixture
def time() -> FakeTime:
    return FakeTime()


@pytest.fixture
def gateway(live: FakeLive, replay: ReplayGateway, time: FakeTime) -> FallbackGateway:
    return FallbackGateway(live, replay, monotonic=time)


def test_the_fall_back_satisfies_the_gateway_port_and_the_paired_lookup(gateway: FallbackGateway) -> None:
    assert isinstance(gateway, ValioGateway)
    assert isinstance(gateway, PairedLookup)
    # The port's own `source` is the one asked first and the one the clock belongs to; each answer states
    # its own, and `state()` says where the last look came from.
    assert gateway.source is DataSource.LIVE


def test_closing_the_fall_back_closes_the_live_client_and_is_harmless_without_one(
    gateway: FallbackGateway, live: FakeLive, replay: ReplayGateway
) -> None:
    gateway.close()
    FallbackGateway(replay, replay).close()  # the capture has nothing to close

    assert live.closed is True


def test_while_the_live_api_answers_the_answer_and_the_clock_are_live(gateway: FallbackGateway, live: FakeLive) -> None:
    price = gateway.price(IDS)
    availability = gateway.availability(IDS, fresh=True)

    assert (price.source, availability.source) == (DataSource.LIVE, DataSource.LIVE)
    assert gateway.state().last_source is DataSource.LIVE
    assert gateway.clock.now() == live.NOW
    assert live.calls == 2


# --- one look, one source (finding 1) -------------------------------------------------------------------


def test_one_look_asks_the_live_api_for_price_and_availability_and_both_are_live(
    gateway: FallbackGateway, live: FakeLive
) -> None:
    price, availability = gateway.look_up(IDS, fresh=True)

    assert (price.source, availability.source) == (DataSource.LIVE, DataSource.LIVE)
    assert live.asked == [PRICE, AVAILABILITY]
    assert gateway.state().last_source is DataSource.LIVE


def test_when_availability_fails_after_a_live_price_both_come_from_the_capture(
    gateway: FallbackGateway, live: FakeLive, replay: ReplayGateway
) -> None:
    live.failing = {AVAILABILITY}

    price, availability = gateway.look_up(IDS)

    assert live.asked == [PRICE, AVAILABILITY]  # the live price was fetched, and then thrown away
    assert (price, availability) == (replay.price(IDS), replay.availability(IDS))
    assert (price.source, availability.source) == (DataSource.REPLAY, DataSource.REPLAY)
    assert gateway.state().last_source is DataSource.REPLAY


def test_when_the_price_call_fails_availability_is_not_asked_live(
    gateway: FallbackGateway, live: FakeLive
) -> None:
    live.failing = {PRICE}

    price, availability = gateway.look_up(IDS)

    assert live.asked == [PRICE]
    assert (price.source, availability.source) == (DataSource.REPLAY, DataSource.REPLAY)


@pytest.mark.parametrize(
    ("remaining", "expected", "live_calls"),
    [
        (MIN_CALLS_REMAINING + 1, DataSource.LIVE, 2),
        (MIN_CALLS_REMAINING, DataSource.REPLAY, 0),  # one call could be made, a look needs two
        (0, DataSource.REPLAY, 0),
    ],
)
def test_a_budget_that_cannot_cover_both_calls_sends_the_whole_look_to_the_capture(
    live: FakeLive, replay: ReplayGateway, remaining: int, expected: DataSource, live_calls: int
) -> None:
    live.calls_remaining = remaining
    gateway = FallbackGateway(live, replay)

    price, availability = gateway.look_up(IDS)

    assert LIVE_CALLS_PER_LOOK == 2
    assert (price.source, availability.source) == (expected, expected)
    assert live.calls == live_calls


def test_a_failing_capture_is_reported_and_not_hidden(
    gateway: FallbackGateway, live: FakeLive, replay: ReplayGateway, monkeypatch: Any
) -> None:
    live.down = True

    def unusable(product_ids: Sequence[str], *, fresh: bool = False) -> PriceResponse:
        raise SupplierUnavailable("The replay capture cannot be used.")

    monkeypatch.setattr(replay, "price", unusable)

    with pytest.raises(SupplierUnavailable):
        gateway.price(IDS)
    with pytest.raises(SupplierUnavailable):
        gateway.look_up(IDS)
    assert gateway.state().last_source is None  # no look was completed


# --- the pause after a failure, the budget floor ----------------------------------------------------------


def test_when_the_live_api_fails_the_capture_answers_and_the_next_call_does_not_try_live(
    gateway: FallbackGateway, live: FakeLive, replay: ReplayGateway
) -> None:
    live.down = True

    availability = gateway.availability(IDS)
    price = gateway.price(IDS)

    assert availability == replay.availability(IDS)
    assert price == replay.price(IDS)
    assert gateway.state().last_source is DataSource.REPLAY
    assert live.calls == 1  # the price call right after did not go to the live API


def test_the_live_api_is_asked_again_after_a_pause(gateway: FallbackGateway, live: FakeLive, time: FakeTime) -> None:
    live.down = True
    gateway.look_up(IDS)
    live.down = False

    time.seconds += RETRY_LIVE_AFTER_SECONDS - 1
    still = gateway.look_up(IDS)
    paused = gateway.state().live_paused
    time.seconds += 2
    back = gateway.look_up(IDS)

    assert [answer.source for answer in still] == [DataSource.REPLAY] * 2
    assert paused is True
    assert [answer.source for answer in back] == [DataSource.LIVE] * 2
    assert gateway.state().live_paused is False
    assert gateway.state().last_source is DataSource.LIVE


@pytest.mark.parametrize(
    ("remaining", "expected"),
    [(MIN_CALLS_REMAINING, DataSource.LIVE), (MIN_CALLS_REMAINING - 1, DataSource.REPLAY), (0, DataSource.REPLAY)],
)
def test_with_fewer_than_ten_calls_left_the_capture_answers_and_no_call_is_spent(
    live: FakeLive, replay: ReplayGateway, remaining: int, expected: DataSource
) -> None:
    live.calls_remaining = remaining
    gateway = FallbackGateway(live, replay)

    assert MIN_CALLS_REMAINING == 10
    assert gateway.availability(IDS).source is expected
    assert live.calls == (1 if expected is DataSource.LIVE else 0)
    assert gateway.state().budget_low is (expected is DataSource.REPLAY)


def test_when_the_budget_runs_low_between_two_answers_the_capture_takes_over_and_it_is_logged(
    gateway: FallbackGateway, live: FakeLive, caplog: pytest.LogCaptureFixture
) -> None:
    first = gateway.price(IDS)
    live.calls_remaining = MIN_CALLS_REMAINING - 1

    with caplog.at_level("WARNING", logger="tta.api.fallback"):
        second = gateway.price(IDS)
        third = gateway.price(IDS)

    assert (first.source, second.source, third.source) == (DataSource.LIVE, DataSource.REPLAY, DataSource.REPLAY)
    assert live.calls == 1
    assert caplog.text.count("call budget") == 1  # said once, when the source changes


# --- the data clock and the source (finding 2) ----------------------------------------------------------


def test_before_the_first_look_no_source_is_claimed_whatever_the_budget(gateway: FallbackGateway) -> None:
    state = gateway.state()

    assert state.last_source is None
    assert (state.live_paused, state.budget_low) == (False, False)


def test_in_live_mode_the_data_clock_is_the_live_clock_also_while_the_capture_answers(
    gateway: FallbackGateway, live: FakeLive, replay: ReplayGateway
) -> None:
    before = gateway.clock.now()
    live.down = True

    _, availability = gateway.look_up(IDS)

    assert availability.source is DataSource.REPLAY
    assert availability.time_now == replay.time_now  # the answer still carries the capture's own time
    assert before == gateway.clock.now() == live.NOW != replay.time_now


# --- live looks per minute (finding 4) ------------------------------------------------------------------


def test_at_most_six_looks_a_minute_reach_the_supplier_and_the_rest_come_from_the_capture(
    gateway: FallbackGateway, live: FakeLive, time: FakeTime, caplog: pytest.LogCaptureFixture
) -> None:
    assert MAX_LIVE_LOOKS_PER_MINUTE == 6
    with caplog.at_level("WARNING", logger="tta.api.fallback"):
        sources = []
        for _ in range(MAX_LIVE_LOOKS_PER_MINUTE + 2):
            time.seconds += 1
            sources.append(gateway.look_up(IDS, fresh=True)[1].source)

    assert sources == [DataSource.LIVE] * MAX_LIVE_LOOKS_PER_MINUTE + [DataSource.REPLAY] * 2  # no error
    assert live.calls == MAX_LIVE_LOOKS_PER_MINUTE * LIVE_CALLS_PER_LOOK
    assert caplog.text.count("a minute") == 1
    assert gateway.state().live_paused is False  # a full minute is not a supplier failure

    time.seconds += 60
    assert gateway.look_up(IDS)[0].source is DataSource.LIVE
