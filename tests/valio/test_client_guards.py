"""What the live client refuses before it sends or trusts anything, and how much it tells a caller (SPEC section 10).

An address that would send the key in clear text, an answer too large to be one, a server time far
from ours; and the calls left in the budget, so a caller can turn to replay in time.
"""

from __future__ import annotations

import logging
import traceback
from datetime import timedelta

import httpx
import pytest

from tta.config import Settings
from tta.contracts.errors import SupplierUnavailable

MILK = "464306"
TWENTY_MB = 20 * 1024 * 1024


def with_base_url(settings: Settings, url: str) -> Settings:
    return settings.model_copy(update={"valio_aimo_base_url": url})


def with_budget(settings: Settings, limit: int) -> Settings:
    return settings.model_copy(update={"tta_valio_call_budget": limit})


@pytest.mark.parametrize(
    "url",
    [
        "http://valio.test/api",
        "http://junction26.valioaimo.fi/api",
        "ftp://valio.test/api",
        "ws://localhost/api",
        "valio.test/api",
        "//valio.test/api",
        "",
        "https://",
        "https:///api",
        "http://localhost.valio.test/api",
        "http://127.0.0.1.valio.test/api",
        "http://127.0.0.1@valio.test/api",
        "http://localhost@valio.test/api",
        "http://0.0.0.0:8000/api",
        "http://192.168.1.10:8000/api",
        "http://[::1/api",
    ],
)
def test_a_base_url_that_is_not_https_is_refused_when_the_client_is_built(
    make_client, fake_api, live_settings, url: str
) -> None:
    with pytest.raises(SupplierUnavailable) as raised:
        make_client(fake_api, with_base_url(live_settings, url))

    assert "https" in raised.value.detail
    assert fake_api.requests == []


@pytest.mark.parametrize(
    "url",
    [
        "https://valio.test/api",
        "https://valio.test/api/",
        "HTTPS://valio.test/api",
        "https://localhost/api",
        "http://localhost:8000/api",
        "http://127.0.0.1:8000/api",
        "http://127.8.9.10/api",
        "http://[::1]:8000/api",
    ],
)
def test_https_is_accepted_and_plain_http_only_for_a_loopback_host(
    make_client, fake_api, live_settings, sentinel_key, url: str
) -> None:
    client = make_client(fake_api, with_base_url(live_settings, url))

    client.price([MILK])

    (request,) = fake_api.requests
    assert request.url.path == "/api/price"
    assert request.headers["X-API-Key"] == sentinel_key


def test_a_refused_base_url_is_not_repeated_in_the_error_or_in_the_log(
    make_client, fake_api, live_settings, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    url = "http://operator:plain-text-marker@internal-host.valio.test/api"

    with pytest.raises(SupplierUnavailable) as raised:
        make_client(fake_api, with_base_url(live_settings, url))

    error = raised.value
    shown = " ".join([str(error), repr(error), error.detail, error.to_problem().model_dump_json(),
                      "".join(traceback.format_exception(error)), *(record.getMessage() for record in caplog.records)])
    for part in ("plain-text-marker", "operator", "internal-host", "valio.test"):
        assert part not in shown
    assert error.__cause__ is None and error.__context__ is None
    assert [record.levelno for record in caplog.records] == [logging.WARNING]
    assert "VALIO_AIMO_BASE_URL" in caplog.records[0].getMessage()
    assert "VALIO_AIMO_BASE_URL" not in error.detail


def test_an_answer_over_20_mb_is_refused_before_it_is_parsed_or_recorded(make_client, fake_api, live_settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        answer = fake_api(request).content
        # White space after a body is still valid JSON: only the size is wrong.
        return httpx.Response(200, content=answer + b" " * (TWENTY_MB + 1 - len(answer)))

    client = make_client(handler)

    with pytest.raises(SupplierUnavailable) as raised:
        client.price([MILK])

    assert "20 MB" in raised.value.detail
    assert not (live_settings.tta_data_dir / "recordings").exists()


def test_an_answer_of_exactly_20_mb_is_still_read(make_client, fake_api) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        answer = fake_api(request).content
        return httpx.Response(200, content=answer + b" " * (TWENTY_MB - len(answer)))

    client = make_client(handler)

    assert client.price([MILK]).by_id()[MILK].has_price


def test_an_answer_with_a_server_time_far_from_ours_is_refused_not_recorded_and_not_cached(
    make_client, live_settings, fake_time
) -> None:
    attempts: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        entry = {"productId": MILK, "salesBlock": False, "scheduleLines": []}
        return httpx.Response(200, json={"timeNow": "2020-01-01T00:00:00+0200", "products": [entry]})

    client = make_client(handler)

    for _ in range(2):
        with pytest.raises(SupplierUnavailable) as raised:
            client.availability([MILK])

    assert "12 hours" in raised.value.detail
    assert len(attempts) == 2
    assert not (live_settings.tta_data_dir / "recordings").exists()
    assert client.clock.now() == fake_time.utc_now()  # the clock was not moved


def test_an_answer_with_an_older_server_time_is_used_and_does_not_turn_the_clock_back(
    make_client, fake_api, fake_time, capture_demo
) -> None:
    client = make_client(fake_api)
    client.availability([MILK])
    fake_time.advance(300)

    answer = client.availability([MILK], fresh=True)  # the fake API states the capture's time again

    assert answer.time_now == capture_demo.time_now
    assert client.clock.now() == capture_demo.time_now + timedelta(seconds=300)


def test_calls_remaining_counts_down_with_every_call_sent_and_not_with_a_cached_answer(
    make_client, fake_api, live_settings
) -> None:
    client = make_client(fake_api, with_budget(live_settings, 3))
    at_the_start = client.calls_remaining

    client.price([MILK])
    client.price([MILK])  # from the cache
    client.availability([MILK])

    assert at_the_start == 3
    assert client.calls_remaining == 1
    assert len(fake_api.requests) == 2  # asking what is left sends nothing


def test_calls_remaining_is_zero_once_the_budget_is_spent(make_client, fake_api, live_settings) -> None:
    client = make_client(fake_api, with_budget(live_settings, 1))

    client.price([MILK])

    assert client.calls_remaining == 0


def test_calls_remaining_is_shared_by_every_client_on_the_data_directory(make_client, fake_api, live_settings) -> None:
    settings = with_budget(live_settings, 5)
    first, second = make_client(fake_api, settings), make_client(fake_api, settings)

    first.price([MILK])
    second.price([MILK])

    assert first.calls_remaining == second.calls_remaining == 3
