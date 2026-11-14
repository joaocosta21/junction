"""The live client: headers, chunks, spacing, cache, call budget and retries (SPEC section 10)."""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from tta.config import Settings
from tta.contracts.common import DataSource
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.ports import ValioGateway
from tta.valio import CallBudget

MILK = "464306"
OTHER_MILK = "469363"


def with_budget(settings: Settings, limit: int) -> Settings:
    return settings.model_copy(update={"tta_valio_call_budget": limit})


def calls_used(settings: Settings) -> int:
    return CallBudget.for_settings(settings).used


def test_the_client_satisfies_the_gateway_port_and_says_it_is_live(make_client, fake_api) -> None:
    client = make_client(fake_api)

    assert isinstance(client, ValioGateway)
    assert client.source is DataSource.LIVE


def test_a_call_carries_the_key_an_explicit_user_agent_and_the_three_body_fields(
    make_client, fake_api, sentinel_key
) -> None:
    client = make_client(fake_api)

    client.price([MILK])

    request = fake_api.requests[0]
    body = json.loads(request.content)
    assert request.method == "POST"
    assert str(request.url) == "https://valio.test/api/price"
    assert request.headers["X-API-Key"] == sentinel_key
    assert request.headers["Accept"] == "application/json"
    # Cloudflare refuses Python's default user agent (AIMO/FINDINGS.md section 1).
    assert request.headers["User-Agent"].startswith("tta-gateway/")
    assert set(body) == {"customer", "requestedDate", "products"}
    assert body["customer"] == "123"
    assert body["products"] == [MILK]
    assert date.fromisoformat(body["requestedDate"])


def test_availability_goes_to_its_own_path_and_parses_the_answer(make_client, fake_api, capture_demo) -> None:
    client = make_client(fake_api)

    response = client.availability([MILK, OTHER_MILK])

    assert str(fake_api.requests[0].url) == "https://valio.test/api/availability"
    assert response.source is DataSource.LIVE
    assert response.time_now == capture_demo.time_now
    assert [line.product_id for line in response.lines] == [MILK, OTHER_MILK]
    assert response.by_id()[OTHER_MILK].schedule_line.available_amount == 384


def test_2300_ids_make_three_calls_at_least_a_second_apart(make_client, fake_api, fake_time) -> None:
    client = make_client(fake_api)
    ids = [str(900_000 + number) for number in range(2_300)]

    response = client.price(ids)

    assert [len(chunk) for chunk in fake_api.sent_ids()] == [1_000, 1_000, 300]
    assert [line.product_id for line in response.lines] == ids
    assert len(fake_time.sleeps) == 2
    assert all(seconds >= 1.0 for seconds in fake_time.sleeps)


def test_calls_to_different_endpoints_are_also_a_second_apart(make_client, fake_api, fake_time) -> None:
    client = make_client(fake_api)

    client.price([MILK])
    client.availability([MILK])

    assert fake_time.sleeps == [1.0]


def test_no_wait_when_a_second_has_already_passed(make_client, fake_api, fake_time) -> None:
    client = make_client(fake_api)

    client.price([MILK])
    fake_time.advance(5)
    client.availability([MILK])

    assert fake_time.sleeps == []


def test_duplicate_ids_are_sent_once_and_lines_follow_the_order_asked(make_client, fake_api) -> None:
    client = make_client(fake_api)

    response = client.availability([OTHER_MILK, MILK, OTHER_MILK])

    assert fake_api.sent_ids() == [[OTHER_MILK, MILK]]
    assert [line.product_id for line in response.lines] == [OTHER_MILK, MILK]


def test_a_repeated_call_inside_60_seconds_makes_no_request(make_client, fake_api, fake_time) -> None:
    client = make_client(fake_api)
    first = client.availability([MILK, OTHER_MILK])
    fake_time.advance(59)

    second = client.availability([OTHER_MILK, MILK])

    assert len(fake_api.requests) == 1
    assert second == first


def test_a_fresh_call_skips_the_cache_and_asks_again(make_client, fake_api, fake_time) -> None:
    client = make_client(fake_api)
    client.availability([MILK])
    client.price([MILK])
    fake_time.advance(5)

    client.availability([MILK], fresh=True)
    client.price([MILK], fresh=True)

    assert len(fake_api.requests) == 4


def test_after_60_seconds_the_same_call_asks_again(make_client, fake_api, fake_time) -> None:
    client = make_client(fake_api)
    client.availability([MILK])
    fake_time.advance(61)

    client.availability([MILK])

    assert len(fake_api.requests) == 2


def test_the_cache_is_kept_per_endpoint_and_per_id_set(make_client, fake_api) -> None:
    client = make_client(fake_api)

    client.availability([MILK])
    client.price([MILK])
    client.price([MILK, OTHER_MILK])
    client.availability([MILK])
    client.price([MILK])

    assert [request.url.path.rsplit("/", 1)[-1] for request in fake_api.requests] == [
        "availability", "price", "price",
    ]


def test_the_budget_stops_the_next_call_with_the_typed_error(
    make_client, fake_api, live_settings, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING, logger="tta.valio.budget")
    client = make_client(fake_api, with_budget(live_settings, 2))
    client.price([MILK])
    client.availability([MILK])

    with pytest.raises(SupplierUnavailable) as raised:
        client.price([OTHER_MILK])

    assert len(fake_api.requests) == 2
    # The detail is public: the count and the setting are in the log, not in what the caller reads.
    assert "cannot be asked right now" in raised.value.detail
    assert "2 of 2" not in raised.value.detail and "TTA_VALIO_CALL_BUDGET" not in raised.value.detail
    (record,) = caplog.records
    assert "2 of 2" in record.getMessage() and "TTA_VALIO_CALL_BUDGET" in record.getMessage()


def test_the_budget_is_persisted_and_holds_after_a_restart(make_client, fake_api, live_settings) -> None:
    settings = with_budget(live_settings, 1)
    make_client(fake_api, settings).price([MILK])
    restarted = make_client(fake_api, settings)

    with pytest.raises(SupplierUnavailable):
        restarted.price([MILK])

    assert len(fake_api.requests) == 1
    assert (settings.tta_data_dir / "valio_call_budget.json").is_file()


def test_an_answer_from_the_cache_costs_no_budget(make_client, fake_api, live_settings) -> None:
    client = make_client(fake_api, with_budget(live_settings, 1))

    client.price([MILK])
    client.price([MILK])

    assert calls_used(live_settings) == 1


def test_a_time_out_is_retried_twice_then_reported_as_supplier_unavailable(
    make_client, fake_time, live_settings
) -> None:
    attempts: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        raise httpx.ReadTimeout("timed out", request=request)

    client = make_client(handler)

    with pytest.raises(SupplierUnavailable) as raised:
        client.availability([MILK])

    assert len(attempts) == 3
    assert fake_time.sleeps == [1.0, 2.0]  # back-off before each retry
    assert "3 attempts" in raised.value.detail
    assert "timed out" in raised.value.detail
    assert calls_used(live_settings) == 3  # every attempt reached the API


def test_a_5xx_is_retried_and_a_later_good_answer_is_used(make_client, fake_api) -> None:
    statuses = iter([503, 500])
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        status = next(statuses, 200)
        attempts.append(status)
        return fake_api(request) if status == httpx.codes.OK else httpx.Response(status, text="upstream error")

    client = make_client(handler)

    response = client.price([MILK])

    assert attempts == [503, 500, 200]
    assert response.by_id()[MILK].has_price


def test_three_5xx_answers_end_in_supplier_unavailable(make_client) -> None:
    attempts: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        return httpx.Response(502, text="bad gateway")

    client = make_client(handler)

    with pytest.raises(SupplierUnavailable) as raised:
        client.price([MILK])

    assert len(attempts) == 3
    assert "HTTP 502" in raised.value.detail


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422, 429])
def test_a_4xx_is_reported_at_once_and_never_retried(make_client, fake_time, status: int) -> None:
    attempts: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        return httpx.Response(status, json={"detail": "refused"})

    client = make_client(handler)

    with pytest.raises(SupplierUnavailable) as raised:
        client.price([MILK])

    assert len(attempts) == 1
    assert fake_time.sleeps == []
    assert f"HTTP {status}" in raised.value.detail


def test_a_403_carries_the_user_agent_hint(make_client) -> None:
    client = make_client(lambda request: httpx.Response(403, text="<html>Just a moment...</html>"))

    with pytest.raises(SupplierUnavailable) as raised:
        client.availability([MILK])

    assert "User-Agent" in raised.value.detail
    assert "Cloudflare" in raised.value.detail


def test_a_connection_failure_is_reported_and_not_retried(make_client) -> None:
    attempts: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        raise httpx.ConnectError("connection refused", request=request)

    client = make_client(handler)

    with pytest.raises(SupplierUnavailable) as raised:
        client.price([MILK])

    assert len(attempts) == 1
    assert "ConnectError" in raised.value.detail


@pytest.mark.parametrize("key", [None, SecretStr("   ")], ids=["no key", "a blank key"])
def test_without_a_key_no_call_is_made_and_no_budget_is_spent(
    make_client, fake_api, live_settings, caplog: pytest.LogCaptureFixture, key: SecretStr | None
) -> None:
    caplog.set_level(logging.WARNING, logger="tta.valio.client")
    client = make_client(fake_api, live_settings.model_copy(update={"valio_aimo_api_key": key}))

    with pytest.raises(SupplierUnavailable) as raised:
        client.price([MILK])

    assert fake_api.requests == []
    assert calls_used(live_settings) == 0
    # The detail is public: which setting of ours is missing is in the log, not in what the caller reads.
    assert "cannot be asked right now" in raised.value.detail
    assert "VALIO_AIMO_API_KEY" not in raised.value.detail
    (record,) = caplog.records
    assert record.levelno == logging.WARNING
    assert "VALIO_AIMO_API_KEY" in record.getMessage() and "/price" in record.getMessage()


@pytest.mark.parametrize("text", ["<html>maintenance</html>", "[]", '{"currency": "EUR"}'])
def test_an_answer_that_cannot_be_read_is_reported_and_not_cached(make_client, text: str) -> None:
    attempts: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        return httpx.Response(200, text=text)

    client = make_client(handler)

    for _ in range(2):
        with pytest.raises(SupplierUnavailable):
            client.price([MILK])

    assert len(attempts) == 2


def test_an_answer_that_leaves_out_a_requested_product_is_refused(make_client) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        entry = {"productId": MILK, "salesBlock": False, "scheduleLines": []}
        return httpx.Response(200, json={"timeNow": "2026-11-14T02:52:45+0200", "products": [entry]})

    client = make_client(handler)

    with pytest.raises(SupplierUnavailable) as raised:
        client.availability([MILK, OTHER_MILK])

    assert "1 of the 2" in raised.value.detail


def test_products_nobody_asked_for_are_dropped_from_the_answer(make_client) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        entries = [{"productId": pid, "salesBlock": False, "scheduleLines": []} for pid in (MILK, "999000")]
        return httpx.Response(200, json={"timeNow": "2026-11-14T02:52:45+0200", "products": entries})

    client = make_client(handler)

    response = client.availability([MILK])

    assert [line.product_id for line in response.lines] == [MILK]


def test_no_ids_means_no_call_and_an_empty_answer(make_client, fake_api) -> None:
    client = make_client(fake_api)

    price = client.price([])
    availability = client.availability([])

    assert fake_api.requests == []
    assert price.lines == () and price.source is DataSource.LIVE and price.currency == "EUR"
    assert availability.lines == () and availability.time_now.utcoffset() is not None


def test_a_single_string_is_not_taken_for_a_list_of_ids(make_client, fake_api) -> None:
    client = make_client(fake_api)

    with pytest.raises(TypeError):
        client.price(MILK)

    assert fake_api.requests == []


def test_an_availability_answer_sets_the_clock_to_the_server_time(make_client, fake_api, capture_demo) -> None:
    client = make_client(fake_api)

    client.availability([MILK])

    assert client.clock.now() == capture_demo.time_now


def test_an_answer_from_the_cache_does_not_turn_the_clock_back(make_client, fake_api, fake_time, capture_demo) -> None:
    client = make_client(fake_api)
    client.availability([MILK])
    fake_time.advance(30)

    client.availability([MILK])

    assert client.clock.now() == capture_demo.time_now + timedelta(seconds=30)


def test_a_price_answer_is_stamped_with_the_clock(make_client, fake_api, fake_time, capture_demo) -> None:
    client = make_client(fake_api)
    client.availability([MILK])
    fake_time.advance(10)

    price = client.price([MILK])

    assert price.retrieved_at == capture_demo.time_now + timedelta(seconds=10)


def test_availability_over_several_chunks_reports_the_latest_server_time(make_client) -> None:
    times = iter(["2026-11-14T02:52:45+0200", "2026-11-14T02:52:47+0200"])

    def handler(request: httpx.Request) -> httpx.Response:
        ids = json.loads(request.content)["products"]
        entries: list[dict[str, Any]] = [{"productId": pid, "salesBlock": False, "scheduleLines": []} for pid in ids]
        return httpx.Response(200, json={"timeNow": next(times), "products": entries})

    client = make_client(handler)

    response = client.availability([str(900_000 + number) for number in range(1_001)])

    assert response.time_now == datetime.fromisoformat("2026-11-14T02:52:47+02:00")
    assert len(response.lines) == 1_001


def test_calls_from_several_threads_are_made_one_at_a_time(make_client, fake_api, live_settings) -> None:
    client = make_client(fake_api)
    ids = [str(900_000 + number) for number in range(8)]

    with ThreadPoolExecutor(max_workers=8) as pool:
        answers = list(pool.map(lambda product_id: client.price([product_id]), ids))

    assert [answer.lines[0].product_id for answer in answers] == ids
    assert len(fake_api.requests) == 8
    assert calls_used(live_settings) == 8  # no count lost between threads


def test_closing_the_client_closes_its_connection_pool(make_client, fake_api) -> None:
    client = make_client(fake_api)

    client.close()

    with pytest.raises(RuntimeError):
        client.price([MILK])
