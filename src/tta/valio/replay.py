"""The `ValioGateway` port answered from a capture folder of `fixtures/valio/` (SPEC section 10).

No network and no key. The clock is pinned to the capture's `timeNow`, so a demo gives the same
answer whatever the hour, and survives the mock API being down.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn

from tta.contracts.availability import AvailabilityLine, AvailabilityResponse, PriceLine, PriceResponse
from tta.contracts.common import CURRENCY_EUR, DataSource
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


def unknown_price_line(product_id: str) -> PriceLine:
    """What /api/price answers for an id it does not know: `error` true (AIMO/docs/API.md section 8.5)."""
    return PriceLine(product_id=product_id, error=True, net_price_found=False)


def unknown_availability_line(product_id: str) -> AvailabilityLine:
    """What /api/availability answers for an unknown id: the shape of a product that cannot be delivered."""
    return AvailabilityLine(product_id=product_id, sales_block=False)


class ReplayGateway:
    """Price and availability as one capture recorded them. An id outside the capture reads as unknown."""

    def __init__(self, capture_dir: Path) -> None:
        self._name = capture_dir.name
        time_now, files = _read_manifest(capture_dir)
        price_parts = [
            _read_part(path, self._name, lambda body: parse_price_body(body, DataSource.REPLAY, time_now))
            for path in files[PRICE_ENDPOINT]
        ]
        availability_parts = [
            _read_part(path, self._name, lambda body: parse_availability_body(body, DataSource.REPLAY))
            for path in files[AVAILABILITY_ENDPOINT]
        ]
        self._time_now = time_now
        self._prices = {line.product_id: line for part in price_parts for line in part.lines}
        self._availability = {line.product_id: line for part in availability_parts for line in part.lines}
        self._currency = price_parts[0].currency if price_parts else CURRENCY_EUR
        self._pricing_date = price_parts[0].pricing_date if price_parts else None
        self._requested_date = availability_parts[0].requested_date if availability_parts else None

    @property
    def source(self) -> DataSource:
        return DataSource.REPLAY

    @property
    def time_now(self) -> datetime:
        """The server time of the capture: the instant every cut-off is compared with in replay."""
        return self._time_now

    @property
    def clock(self) -> PinnedClock:
        return PinnedClock(self._time_now)

    def price(self, product_ids: Sequence[str], *, fresh: bool = False) -> PriceResponse:  # noqa: ARG002
        lines = tuple(
            self._prices[product_id] if product_id in self._prices else unknown_price_line(product_id)
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
            else unknown_availability_line(product_id)
            for product_id in distinct_ids(product_ids)
        )
        return AvailabilityResponse(
            time_now=self._time_now, requested_date=self._requested_date, lines=lines, source=DataSource.REPLAY
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


def _read_manifest(capture_dir: Path) -> tuple[datetime, dict[str, tuple[Path, ...]]]:
    """The capture's `timeNow` and its body files. The manifest is a data file, so nothing in it is trusted."""
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
    return time_now, files


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
