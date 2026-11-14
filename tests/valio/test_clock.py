"""The two clocks behind the `Clock` port: the server's time in live mode, a pinned instant in replay."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tta.contracts.ports import Clock
from tta.valio import LiveClock, PinnedClock

SERVER_TIME = datetime.fromisoformat("2026-11-14T02:52:45+02:00")


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
