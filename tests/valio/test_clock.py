"""The two clocks behind the `Clock` port: the server's time in live mode, a pinned instant in replay."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from tta.contracts.errors import SupplierUnavailable
from tta.contracts.ports import Clock
from tta.valio import LiveClock, PinnedClock

SERVER_TIME = datetime.fromisoformat("2026-11-14T02:52:45+02:00")
HELSINKI = timezone(timedelta(hours=2))
TWELVE_HOURS = timedelta(hours=12)


def test_both_clocks_satisfy_the_port() -> None:
    assert isinstance(LiveClock(), Clock)
    assert isinstance(PinnedClock(SERVER_TIME), Clock)


def test_a_pinned_clock_always_answers_its_instant() -> None:
    clock = PinnedClock(SERVER_TIME)

    assert clock.now() == SERVER_TIME
    assert clock.now() == SERVER_TIME


def test_a_pinned_clock_refuses_a_time_without_an_offset() -> None:
    with pytest.raises(ValueError, match="offset"):
        PinnedClock(datetime(2026, 11, 14, 2, 52, 45))  # noqa: DTZ001


def test_a_live_clock_answers_utc_now_before_any_response() -> None:
    before = datetime.now(UTC)

    now = LiveClock().now()

    assert now.utcoffset() == timedelta(0)
    assert before <= now <= datetime.now(UTC)


def test_a_live_clock_answers_the_time_now_of_the_last_response(fake_time) -> None:
    clock = LiveClock(utc_now=fake_time.utc_now)

    clock.observe(SERVER_TIME)

    assert clock.now() == SERVER_TIME
    assert clock.now().utcoffset() == timedelta(hours=2)


def test_a_live_clock_carries_the_server_time_forward_between_responses(fake_time) -> None:
    clock = LiveClock(utc_now=fake_time.utc_now)
    clock.observe(SERVER_TIME)

    fake_time.advance(90)

    assert clock.now() == SERVER_TIME + timedelta(seconds=90)


def test_a_newer_response_replaces_the_older_one(fake_time) -> None:
    clock = LiveClock(utc_now=fake_time.utc_now)
    clock.observe(SERVER_TIME)
    fake_time.advance(90)

    clock.observe(SERVER_TIME + timedelta(seconds=95))

    assert clock.now() == SERVER_TIME + timedelta(seconds=95)


def test_a_live_clock_refuses_a_time_without_an_offset() -> None:
    with pytest.raises(ValueError, match="offset"):
        LiveClock().observe(datetime(2026, 11, 14, 2, 52, 45))  # noqa: DTZ001


@pytest.mark.parametrize(
    "away",
    [TWELVE_HOURS + timedelta(seconds=1), -TWELVE_HOURS - timedelta(seconds=1), timedelta(days=-3650),
     timedelta(days=3650)],
)
def test_a_live_clock_refuses_a_server_time_more_than_12_hours_from_this_machine(fake_time, away: timedelta) -> None:
    clock = LiveClock(utc_now=fake_time.utc_now)
    clock.observe(SERVER_TIME)

    with pytest.raises(SupplierUnavailable) as raised:
        clock.observe((fake_time.utc_now() + away).astimezone(HELSINKI))

    assert "12 hours" in raised.value.detail
    assert clock.now() == SERVER_TIME  # the refused time moved nothing


@pytest.mark.parametrize("away", [TWELVE_HOURS, -TWELVE_HOURS])
def test_a_server_time_exactly_12_hours_from_this_machine_is_still_taken(fake_time, away: timedelta) -> None:
    clock = LiveClock(utc_now=fake_time.utc_now)

    clock.observe((fake_time.utc_now() + away).astimezone(HELSINKI))

    assert clock.now() == fake_time.utc_now() + max(away, timedelta(0))


def test_an_older_server_time_does_not_turn_the_clock_back(fake_time) -> None:
    clock = LiveClock(utc_now=fake_time.utc_now)
    clock.observe(SERVER_TIME)
    fake_time.advance(90)

    clock.observe(SERVER_TIME + timedelta(seconds=10))

    assert clock.now() == SERVER_TIME + timedelta(seconds=90)


def test_the_first_server_time_does_not_turn_the_clock_back_either(fake_time) -> None:
    clock = LiveClock(utc_now=fake_time.utc_now)
    before = clock.now()

    clock.observe((fake_time.utc_now() - timedelta(minutes=5)).astimezone(HELSINKI))

    assert clock.now() == before
    assert clock.now().utcoffset() == timedelta(hours=2)  # the instant stays, the server's offset is taken


def test_a_live_clock_never_reads_earlier_than_it_did_whatever_it_is_told(fake_time) -> None:
    clock = LiveClock(utc_now=fake_time.utc_now)
    told = [timedelta(minutes=50), timedelta(minutes=-50), timedelta(hours=11), timedelta(hours=-11), timedelta(0)]
    readings = [clock.now()]

    for away in told:
        fake_time.advance(1)
        clock.observe((fake_time.utc_now() + away).astimezone(HELSINKI))
        readings.append(clock.now())

    assert readings == sorted(readings)
    assert readings[-1] == fake_time.utc_now() + timedelta(hours=11)  # the furthest ahead the server has said
