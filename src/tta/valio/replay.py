"""The `ValioGateway` port answered from a capture folder of `fixtures/valio/` (SPEC section 10).

No network and no key. The clock is pinned to the capture's `timeNow`, so a demo gives the same
answer whatever the hour, and survives the mock API being down. A demo clock (`TTA_DEMO_CLOCK`) pins it
to an instant we chose instead; each availability answer says which of the two its `time_now` is.

A capture's manifest may join later recordings (`joined_recordings`, task CK): the first recording gives the
clock and wins wherever both hold a product; a product only a later one holds is answered from it, and the
gateway says which recording answered and when it was made (`recording_of`, `recorded_at_of`, `join_sentence`).
Valio Aimo said on 14 Nov 2026 that its test data is static, which is why two recordings of the same Saturday
are read as one.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn

from tta.availability.wording import format_moment
from tta.config import Settings
from tta.contracts.availability import AvailabilityLine, AvailabilityResponse, PriceLine, PriceResponse
from tta.contracts.common import CURRENCY_EUR, ClockBasis, DataSource
from tta.contracts.errors import SupplierUnavailable
from tta.valio.clock import PinnedClock
from tta.valio.ids import distinct_ids
from tta.valio.parsing import (
    AVAILABILITY_ENDPOINT,
    PRICE_ENDPOINT,
    load_body,
    parse_availability_body,
    parse_price_body,
)

MANIFEST_NAME = "manifest.json"
JOINED_KEY = "joined_recordings"  # in a manifest: the names of sibling capture folders read after this one
JOIN_SENTENCE = (
    "{later:,} of the {total:,} recorded products were recorded later than the rest: {parts}, against {first_at} "
    "for the other {first:,} (recording {first_name}, which gives the clock). Valio Aimo said on 14 Nov 2026 that "
    "its test data is static, which is why two recordings of the same Saturday are read as one."
)


@dataclass(frozen=True)
class LaterRecording:
    """A recording joined to the first one: its name, its own server time, and how many products it answers
    for (those the recordings before it do not hold)."""

    name: str
    recorded_at: datetime
    product_count: int


@dataclass(frozen=True)
class _Recording:
    """One capture folder, parsed."""

    name: str
    recorded_at: datetime
    prices: Mapping[str, PriceLine]
    availability: Mapping[str, AvailabilityLine]
    currency: str | None
    pricing_date: datetime | None
    requested_date: datetime | None
    joined: tuple[str, ...]


def unknown_price_line(product_id: str) -> PriceLine:
    """What /api/price answers for an id it does not know: `error` true (AIMO/docs/API.md section 8.5)."""
    return PriceLine(product_id=product_id, error=True, net_price_found=False)


def unknown_availability_line(product_id: str) -> AvailabilityLine:
    """What /api/availability answers for an unknown id: the shape of a product that cannot be delivered."""
    return AvailabilityLine(product_id=product_id, sales_block=False)


def not_recorded_price_line(product_id: str) -> PriceLine:
    """A price line for an id the capture holds no answer for. It has the shape of the API's answer for an
    unknown id and is marked `not_in_recording`, so nobody reads it as something Valio said."""
    return unknown_price_line(product_id).model_copy(update={"not_in_recording": True})


def not_recorded_availability_line(product_id: str) -> AvailabilityLine:
    """An availability line for an id the capture holds no answer for, marked `not_in_recording`: without the
    mark it would read as "cannot be delivered on any date", which Valio never said about it."""
    return unknown_availability_line(product_id).model_copy(update={"not_in_recording": True})


class ReplayGateway:
    """Price and availability as one capture recorded them. An id outside the capture reads as unknown and is
    marked `not_in_recording` (SPEC section 5, `NOT_IN_RECORDING`)."""

    def __init__(self, capture_dir: Path, *, demo_clock: datetime | None = None) -> None:
        """`demo_clock`: an instant we chose, which then replaces the capture's own `timeNow` as the clock of
        every answer (`Settings.tta_demo_clock`). The recorded prices and availability are not changed."""
        if demo_clock is not None and demo_clock.utcoffset() is None:
            raise ValueError("a demo clock needs a time with an offset, not a naive one")
        first = _read_recording(capture_dir)
        self._name = first.name
        self._recorded_at = first.recorded_at
        self._time_now = demo_clock or first.recorded_at
        self._basis = ClockBasis.RECORDING if demo_clock is None else ClockBasis.DEMO_SETTING
        self._currency = first.currency or CURRENCY_EUR
        self._pricing_date = first.pricing_date
        self._requested_date = first.requested_date
        prices, availability = dict(first.prices), dict(first.availability)
        answered_by: dict[str, _Recording] = dict.fromkeys((*prices, *availability), first)
        later: list[LaterRecording] = []
        for name in first.joined:
            joined = _read_joined(capture_dir, name, first)
            new_ids = [pid for pid in dict.fromkeys((*joined.availability, *joined.prices)) if pid not in answered_by]
            # The first recording wins: a product it holds is never answered from a later one, in whole or in part.
            prices.update({pid: joined.prices[pid] for pid in new_ids if pid in joined.prices})
            availability.update({pid: joined.availability[pid] for pid in new_ids if pid in joined.availability})
            answered_by.update(dict.fromkeys(new_ids, joined))
            later.append(LaterRecording(joined.name, joined.recorded_at, len(new_ids)))
        self._prices, self._availability, self._answered_by = prices, availability, answered_by
        self._later = tuple(later)

    @property
    def source(self) -> DataSource:
        return DataSource.REPLAY

    @classmethod
    def from_settings(cls, settings: Settings) -> ReplayGateway:
        """The capture of the settings, on the demo clock when one is in force (replay mode only)."""
        return cls(settings.replay_capture_dir, demo_clock=settings.demo_clock)

    @property
    def time_now(self) -> datetime:
        """The instant every cut-off is compared with in replay: the server time of the capture, or the demo
        clock when one was set."""
        return self._time_now

    @property
    def recorded_at(self) -> datetime:
        """The server time of the capture itself, whatever the clock is set to."""
        return self._recorded_at

    @property
    def time_basis(self) -> ClockBasis:
        """Whether `time_now` is the recording's own instant or one we set."""
        return self._basis

    @property
    def clock(self) -> PinnedClock:
        return PinnedClock(self._time_now)

    @property
    def product_count(self) -> int:
        """How many products have a recorded answer, over the first recording and those joined to it."""
        return len(self._answered_by)

    @property
    def later_recordings(self) -> tuple[LaterRecording, ...]:
        """The recordings joined to the first one, in the manifest's order; empty for a capture read alone."""
        return self._later

    def recording_of(self, product_id: str) -> str | None:
        """The name of the recording that answers for this product; None when none holds it."""
        recording = self._answered_by.get(product_id)
        return None if recording is None else recording.name

    def recorded_at_of(self, product_id: str) -> datetime | None:
        """The server time of the recording that answers for this product; None when none holds it."""
        recording = self._answered_by.get(product_id)
        return None if recording is None else recording.recorded_at

    def recorded_later(self, product_ids: Sequence[str]) -> tuple[str, ...]:
        """Those of `product_ids` whose answer comes from a recording made after the first one, in order."""
        return tuple(
            pid for pid in distinct_ids(product_ids)
            if pid in self._answered_by and self._answered_by[pid].name != self._name
        )

    @property
    def join_sentence(self) -> str | None:
        """What a person reads about the join: how many products were recorded later, when, and why reading
        them together is honest. None when the capture joins nothing."""
        if not self._later:
            return None
        later = sum(each.product_count for each in self._later)
        parts = ", ".join(f"on {format_moment(each.recorded_at)} (recording {each.name})" for each in self._later)
        return JOIN_SENTENCE.format(
            later=later, total=self.product_count, parts=parts, first_at=format_moment(self._recorded_at),
            first=self.product_count - later, first_name=self._name,
        )

    def price(self, product_ids: Sequence[str], *, fresh: bool = False) -> PriceResponse:  # noqa: ARG002
        lines = tuple(
            self._prices[product_id] if product_id in self._prices else not_recorded_price_line(product_id)
            for product_id in distinct_ids(product_ids)
        )
        return PriceResponse(
            currency=self._currency,
            pricing_date=self._pricing_date,
            lines=lines,
            source=DataSource.REPLAY,
            retrieved_at=self._time_now,
        )

    def availability(self, product_ids: Sequence[str], *, fresh: bool = False) -> AvailabilityResponse:  # noqa: ARG002
        lines = tuple(
            self._availability[product_id]
            if product_id in self._availability
            else not_recorded_availability_line(product_id)
            for product_id in distinct_ids(product_ids)
        )
        return AvailabilityResponse(
            time_now=self._time_now, requested_date=self._requested_date, lines=lines, source=DataSource.REPLAY,
            time_basis=self._basis,
        )


def _unusable(capture: str, why: str) -> NoReturn:
    raise SupplierUnavailable(f"The replay capture {capture} cannot be used: {why}.")


def _read_text(path: Path, capture: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise SupplierUnavailable(
            f"The replay capture {capture} cannot be used: {path.name} cannot be read ({type(error).__name__})."
        ) from error


def recording_instant(capture_dir: Path) -> datetime:
    """The server time of a capture, read from its manifest alone: the clock of replay without loading the
    recorded answers. Raises `SupplierUnavailable` when the manifest cannot be used."""
    return _read_manifest(capture_dir)[0]


def _read_recording(capture_dir: Path) -> _Recording:
    """One capture folder. Raises `SupplierUnavailable` when it cannot be used."""
    name = capture_dir.name
    recorded_at, files, joined = _read_manifest(capture_dir)
    price_parts = [
        _read_part(path, name, lambda body: parse_price_body(body, DataSource.REPLAY))
        for path in files[PRICE_ENDPOINT]
    ]
    availability_parts = [
        _read_part(path, name, lambda body: parse_availability_body(body, DataSource.REPLAY))
        for path in files[AVAILABILITY_ENDPOINT]
    ]
    return _Recording(
        name=name, recorded_at=recorded_at,
        prices={line.product_id: line for part in price_parts for line in part.lines},
        availability={line.product_id: line for part in availability_parts for line in part.lines},
        currency=price_parts[0].currency if price_parts else None,
        pricing_date=price_parts[0].pricing_date if price_parts else None,
        requested_date=availability_parts[0].requested_date if availability_parts else None,
        joined=joined,
    )


def _read_joined(capture_dir: Path, name: str, first: _Recording) -> _Recording:
    """A recording joined to `first`: a sibling folder that answers for the same requested date, pricing date and
    currency. One made for another date is refused: its stock and price say nothing about the date asked. The
    joined recording's own joins are not followed."""
    joined = _read_recording(capture_dir.parent / name)
    for what, own, theirs in (
        ("requested date", first.requested_date, joined.requested_date),
        ("pricing date", first.pricing_date, joined.pricing_date),
        ("currency", first.currency, joined.currency),
    ):
        if own is not None and theirs is not None and own != theirs:
            _unusable(first.name, f"the joined recording {name} has another {what}")
    return joined


def _joined_names(capture_dir: Path, names: Any) -> tuple[str, ...]:
    """The sibling capture folders a manifest joins. A name is a plain folder name, never this capture's own."""
    if names is None:
        return ()
    if not isinstance(names, list):
        _unusable(capture_dir.name, f"{MANIFEST_NAME} has a `{JOINED_KEY}` that is not a list")
    for name in names:
        plain = isinstance(name, str) and name not in ("", ".", "..", capture_dir.name) and Path(name).name == name
        if not plain:
            _unusable(capture_dir.name, f"{MANIFEST_NAME} joins a recording outside the captures folder")
    return tuple(dict.fromkeys(names))


def _read_manifest(capture_dir: Path) -> tuple[datetime, dict[str, tuple[Path, ...]], tuple[str, ...]]:
    """The capture's `timeNow`, its body files and the recordings it joins. The manifest is a data file, so
    nothing in it is trusted."""
    capture = capture_dir.name
    try:
        manifest = json.loads(_read_text(capture_dir / MANIFEST_NAME, capture))
    except (ValueError, RecursionError):
        manifest = None
    if not isinstance(manifest, dict):
        _unusable(capture, f"{MANIFEST_NAME} is not a JSON object")
    try:
        time_now = datetime.fromisoformat(manifest.get("time_now"))
    except (TypeError, ValueError):
        time_now = None
    if time_now is None or time_now.utcoffset() is None:
        _unusable(capture, f"{MANIFEST_NAME} has no `time_now` with an offset")
    listed = manifest.get("files")
    if not isinstance(listed, dict):
        _unusable(capture, f"{MANIFEST_NAME} has no `files`")
    files = {
        endpoint: _body_paths(capture_dir, listed.get(endpoint), endpoint)
        for endpoint in (AVAILABILITY_ENDPOINT, PRICE_ENDPOINT)
    }
    return time_now, files, _joined_names(capture_dir, manifest.get(JOINED_KEY))


def _body_paths(capture_dir: Path, names: Any, endpoint: str) -> tuple[Path, ...]:
    if not isinstance(names, list):
        _unusable(capture_dir.name, f"{MANIFEST_NAME} lists no files for {endpoint}")
    for name in names:
        # A body file is a plain name inside the capture folder: no path may lead out of it.
        if not isinstance(name, str) or not name or Path(name).name != name:
            _unusable(capture_dir.name, f"{MANIFEST_NAME} names a {endpoint} file outside the capture folder")
    return tuple(capture_dir / name for name in names)


def _read_part[Part](path: Path, capture: str, parse: Callable[[dict[str, Any]], Part]) -> Part:
    text = _read_text(path, capture)
    try:
        return parse(load_body(text))
    except SupplierUnavailable as error:
        raise SupplierUnavailable(
            f"The replay capture {capture} cannot be used: {path.name} is not a recorded answer ({error.detail})"
        ) from error
