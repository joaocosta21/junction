"""Live client for the Valio mock API behind the `ValioGateway` port (SPEC section 10).

One client spaces its calls, caches an answer for a minute, stops at the call budget, retries
only what a retry can fix, and records every answer. The key is read from the settings at the
moment a call is sent and goes into the `X-API-Key` header, nowhere else; the client is not built
for an address that would carry that header in clear text.
"""

from __future__ import annotations

import ipaddress
import logging
import threading
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from datetime import datetime

import httpx

from tta.config import Settings
from tta.contracts.availability import AvailabilityResponse, PriceResponse
from tta.contracts.common import CURRENCY_EUR, DataSource
from tta.contracts.errors import SupplierUnavailable
from tta.valio.budget import SUPPLIER_NOT_ASKED, CallBudget
from tta.valio.clock import LiveClock
from tta.valio.ids import distinct_ids
from tta.valio.parsing import (
    AVAILABILITY_ENDPOINT,
    PRICE_ENDPOINT,
    load_body,
    parse_availability_body,
    parse_price_body,
)
from tta.valio.recorder import Recorder

# The API sits behind Cloudflare, which answers 403 to Python's default user agent (AIMO/FINDINGS.md section 1).
USER_AGENT = "tta-gateway/0.1"
MAX_IDS_PER_CALL = 1_000  # a longer list is rejected with HTTP 422 (AIMO/docs/API.md section 2)
MIN_SECONDS_BETWEEN_CALLS = 1.0  # rate limits are undisclosed (AIMO/docs/API.md section 2)
CACHE_SECONDS = 60.0
RETRY_BACKOFF_SECONDS = (1.0, 2.0)  # two retries, on a time-out or a 5xx only
MAX_ATTEMPTS = 1 + len(RETRY_BACKOFF_SECONDS)
CONNECT_TIMEOUT_SECONDS = 5.0
READ_TIMEOUT_SECONDS = 30.0
FIRST_SERVER_ERROR = 500
# The largest recorded answer is 0.5 MB, for 769 ids (fixtures/valio/2026-11-14-demo); one over 20 MB is not read.
MAX_BODY_MEGABYTES = 20
MAX_BODY_BYTES = MAX_BODY_MEGABYTES * 1024 * 1024
ENCRYPTED_SCHEME = "https"
PLAIN_SCHEME = "http"  # accepted for a loopback host only, so a test or a local stand-in needs no certificate
LOOPBACK_HOST_NAME = "localhost"

_REFUSAL_HINTS = {
    401: "the key was rejected",
    403: "the API sits behind Cloudflare, which refuses a call without an explicit User-Agent header; "
    "check that header and the key",
    422: "the request was not accepted",
    429: "the rate limit was reached",
}

logger = logging.getLogger(__name__)

type _Answer = PriceResponse | AvailabilityResponse


class ValioClient:
    """Price and availability from the live mock API. Raises `SupplierUnavailable`, never an httpx error."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
        clock: LiveClock | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settings = settings
        self._base_url = _checked_base_url(settings.valio_aimo_base_url)
        self._http = httpx.Client(
            transport=transport, timeout=httpx.Timeout(READ_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS)
        )
        self._sleep = sleep
        self._monotonic = monotonic
        self._clock = clock or LiveClock()
        self._budget = CallBudget.for_settings(settings)
        self._recorder = Recorder.for_settings(settings)
        self._lock = threading.Lock()  # one call at a time: spacing, budget and cache stay consistent
        self._cache: dict[tuple[str, tuple[str, ...]], tuple[float, _Answer]] = {}
        self._last_call_ended_at: float | None = None

    @property
    def source(self) -> DataSource:
        return DataSource.LIVE

    @property
    def clock(self) -> LiveClock:
        """The server's time as this client last heard it: the clock to hand to the rest of the gateway."""
        return self._clock

    @property
    def calls_remaining(self) -> int:
        """How many calls the budget still allows, zero when none can be made. Reads the count; sends nothing."""
        return self._budget.remaining()

    def close(self) -> None:
        self._http.close()

    def price(self, product_ids: Sequence[str], *, fresh: bool = False) -> PriceResponse:
        ids = distinct_ids(product_ids)
        if not ids:
            return PriceResponse(currency=CURRENCY_EUR, source=DataSource.LIVE, retrieved_at=self._clock.now())
        with self._lock:
            # `fresh` skips the cache: the re-check before an order must see the supplier's current answer.
            cached = None if fresh else self._cached(PRICE_ENDPOINT, ids)
            if isinstance(cached, PriceResponse):
                return cached
            parts = [self._price_chunk(chunk) for chunk in _chunks(ids)]
            response = parts[0].model_copy(update={"lines": tuple(line for part in parts for line in part.lines)})
            self._remember(PRICE_ENDPOINT, ids, response)
            return response

    def availability(self, product_ids: Sequence[str], *, fresh: bool = False) -> AvailabilityResponse:
        ids = distinct_ids(product_ids)
        if not ids:
            return AvailabilityResponse(time_now=self._clock.now(), source=DataSource.LIVE)
        with self._lock:
            # `fresh` skips the cache: the re-check before an order must see the supplier's current answer.
            cached = None if fresh else self._cached(AVAILABILITY_ENDPOINT, ids)
            if isinstance(cached, AvailabilityResponse):
                return cached
            parts = [self._availability_chunk(chunk) for chunk in _chunks(ids)]
            response = parts[0].model_copy(
                update={
                    "lines": tuple(line for part in parts for line in part.lines),
                    # The latest server time of the chunks: the strictest clock for a cut-off.
                    "time_now": max(part.time_now for part in parts),
                }
            )
            self._remember(AVAILABILITY_ENDPOINT, ids, response)
            return response

    def _price_chunk(self, chunk: tuple[str, ...]) -> PriceResponse:
        text = self._call(PRICE_ENDPOINT, chunk)
        retrieved_at = self._clock.now()  # /api/price states no server time
        part = parse_price_body(load_body(text), DataSource.LIVE, retrieved_at)
        answered = part.model_copy(update={"lines": _lines_asked_for(part.by_id(), chunk, PRICE_ENDPOINT)})
        self._record(PRICE_ENDPOINT, chunk, text, retrieved_at)
        return answered

    def _availability_chunk(self, chunk: tuple[str, ...]) -> AvailabilityResponse:
        text = self._call(AVAILABILITY_ENDPOINT, chunk)
        part = parse_availability_body(load_body(text), DataSource.LIVE)
        answered = part.model_copy(update={"lines": _lines_asked_for(part.by_id(), chunk, AVAILABILITY_ENDPOINT)})
        self._clock.observe(part.time_now)
        self._record(AVAILABILITY_ENDPOINT, chunk, text, part.time_now)
        return answered

    def _call(self, endpoint: str, chunk: tuple[str, ...]) -> str:
        """Ask for one chunk and return the body text of a 200 answer. Retries a time-out and a 5xx, nothing else."""
        failure = ""
        for attempt in range(MAX_ATTEMPTS):
            if attempt:
                self._sleep(RETRY_BACKOFF_SECONDS[attempt - 1])
            response = self._send(endpoint, chunk)
            if response is None:
                failure = "timed out"
            elif response.status_code >= FIRST_SERVER_ERROR:
                failure = f"HTTP {response.status_code}"
            else:
                logger.info("Valio /%s: %d ids, HTTP %d", endpoint, len(chunk), response.status_code)
                return self._body_text(endpoint, response)
            logger.warning("Valio /%s: attempt %d of %d failed (%s)", endpoint, attempt + 1, MAX_ATTEMPTS, failure)
        raise SupplierUnavailable(
            f"The Valio API did not answer /{endpoint} after {MAX_ATTEMPTS} attempts (last: {failure})."
        )

    def _send(self, endpoint: str, chunk: tuple[str, ...]) -> httpx.Response | None:
        """One HTTP call, counted against the budget and spaced from the last one. `None` means it timed out."""
        key = self._settings.valio_aimo_api_key
        if key is None or not self._settings.has_valio_key:
            # The detail of the error is public; which setting is missing is for the operator's log.
            logger.warning("Valio /%s was not called: the API key is not set (VALIO_AIMO_API_KEY).", endpoint)
            raise SupplierUnavailable(SUPPLIER_NOT_ASKED)
        self._budget.spend(endpoint)
        self._wait_for_spacing()
        failure = ""
        try:
            return self._http.post(
                f"{self._base_url}/{endpoint}",
                headers={"X-API-Key": key.get_secret_value(), "Accept": "application/json", "User-Agent": USER_AGENT},
                json={
                    "customer": self._settings.tta_customer,
                    # The mock ignores the date (AIMO/docs/API.md section 8.6); the port carries none.
                    "requestedDate": self._clock.now().date().isoformat(),
                    "products": list(chunk),
                },
            )
        except httpx.TimeoutException:
            return None
        except httpx.HTTPError as error:
            failure = type(error).__name__
        finally:
            self._last_call_ended_at = self._monotonic()
        # Raised outside the handler: the httpx error holds the request, and the request holds the key.
        raise SupplierUnavailable(f"The Valio API could not be reached for /{endpoint} ({failure}). Not retried.")

    def _body_text(self, endpoint: str, response: httpx.Response) -> str:
        status = response.status_code
        if status != httpx.codes.OK:
            hint = _REFUSAL_HINTS.get(status)
            reason = f": {hint}" if hint else ""
            raise SupplierUnavailable(f"The Valio API answered /{endpoint} with HTTP {status}{reason}. Not retried.")
        if len(response.content) > MAX_BODY_BYTES:
            raise SupplierUnavailable(
                f"The Valio API answer to /{endpoint} is larger than {MAX_BODY_MEGABYTES} MB, so it was not read "
                "and not recorded."
            )
        text = response.text
        key = self._settings.valio_aimo_api_key
        if key is not None and key.get_secret_value() in text:
            raise SupplierUnavailable(
                f"The Valio API answer to /{endpoint} repeats the API key, so it was not recorded and not used."
            )
        return text

    def _wait_for_spacing(self) -> None:
        if self._last_call_ended_at is None:
            return
        wait = MIN_SECONDS_BETWEEN_CALLS - (self._monotonic() - self._last_call_ended_at)
        if wait > 0:
            self._sleep(wait)

    def _record(self, endpoint: str, chunk: tuple[str, ...], text: str, time_now: datetime) -> None:
        try:
            self._recorder.record(endpoint, chunk, text, time_now)
        except OSError as error:
            raise SupplierUnavailable(
                f"The Valio API answer to /{endpoint} could not be recorded ({error.strerror}), so it was not used."
            ) from error

    def _cached(self, endpoint: str, ids: tuple[str, ...]) -> _Answer | None:
        entry = self._cache.get((endpoint, tuple(sorted(ids))))
        if entry is None:
            return None
        stored_at, response = entry
        return response if self._monotonic() - stored_at < CACHE_SECONDS else None

    def _remember(self, endpoint: str, ids: tuple[str, ...], response: _Answer) -> None:
        now = self._monotonic()
        fresh = {key: entry for key, entry in self._cache.items() if now - entry[0] < CACHE_SECONDS}
        self._cache = {**fresh, (endpoint, tuple(sorted(ids))): (now, response)}


def _checked_base_url(url: str) -> str:
    """The base URL without its last slash. Refused unless it is https, or http to a loopback host.

    The key travels in a request header, so the address must be encrypted. Neither the error nor
    the log repeats the address: it may hold a host name or a password of ours.
    """
    if not _keeps_the_key_private(url):
        logger.warning(
            "No Valio client was built: VALIO_AIMO_BASE_URL is not an https:// address "
            "(http:// is accepted for a loopback host only)."
        )
        raise SupplierUnavailable(
            "The supplier's address is not an https:// address, so no client was built and no call was made."
        )
    return url.rstrip("/")


def _keeps_the_key_private(url: str) -> bool:
    # Read with httpx, which also sends the request: the check and the call see the same host.
    try:
        parsed = httpx.URL(url)
    except httpx.InvalidURL:
        return False  # reported by the caller, outside the handler: the httpx error repeats part of the address
    if not parsed.host:
        return False
    if parsed.scheme == ENCRYPTED_SCHEME:
        return True
    return parsed.scheme == PLAIN_SCHEME and _is_loopback(parsed.host)


def _is_loopback(host: str) -> bool:
    if host == LOOPBACK_HOST_NAME:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False  # a name, not an address: only `localhost` is taken for this machine


def _chunks(ids: tuple[str, ...]) -> Iterator[tuple[str, ...]]:
    for start in range(0, len(ids), MAX_IDS_PER_CALL):
        yield ids[start : start + MAX_IDS_PER_CALL]


def _lines_asked_for[Line](by_id: Mapping[str, Line], ids: tuple[str, ...], endpoint: str) -> tuple[Line, ...]:
    """The answer's lines for the ids asked, in that order. An answer that leaves one out is refused."""
    missing = sum(1 for product_id in ids if product_id not in by_id)
    if missing:
        raise SupplierUnavailable(
            f"The Valio API answer to /{endpoint} leaves out {missing} of the {len(ids)} products asked for."
        )
    return tuple(by_id[product_id] for product_id in ids)
