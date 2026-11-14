"""The API key reaches the `X-API-Key` header and nothing else: no recording, no log record, no error (SPEC 10)."""

from __future__ import annotations

import json
import logging
import traceback
from collections.abc import Callable

import httpx
import pytest

from tta.contracts.errors import SupplierUnavailable

MILK = "464306"


def failing_handlers(key: str) -> dict[str, Callable[[httpx.Request], httpx.Response]]:
    """Every way a call can fail, each one trying to get the key into the error."""

    def time_out(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(f"timed out with {key}", request=request)

    def refuse_connection(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"cannot connect with {key}", request=request)

    def echo_in_entry(request: httpx.Request) -> httpx.Response:
        entry = {"productId": MILK, "quantity": 1.0, "netPriceFound": False, "error": True, "note": key}
        return httpx.Response(200, json={"currency": "EUR", "products": [entry]})

    return {
        "401": lambda request: httpx.Response(401, json={"detail": f"Invalid or missing API key {key}"}),
        "403": lambda request: httpx.Response(403, text=f"<html>blocked {key}</html>"),
        "422": lambda request: httpx.Response(422, json={"detail": [{"input": key, "msg": "too long"}]}),
        "500": lambda request: httpx.Response(500, text=f"trace: X-API-Key={key}"),
        "time-out": time_out,
        "connection": refuse_connection,
        "not json": lambda request: httpx.Response(200, text=f"<html>{key}</html>"),
        "echo": echo_in_entry,
    }


def test_the_key_never_appears_in_a_recording_a_log_record_or_an_exception(
    make_client, fake_api, live_settings, sentinel_key, caplog
) -> None:
    caplog.set_level(logging.DEBUG)
    client = make_client(fake_api)
    client.price([MILK])
    client.availability([MILK])
    errors: list[SupplierUnavailable] = []

    for handler in failing_handlers(sentinel_key).values():
        with pytest.raises(SupplierUnavailable) as raised:
            make_client(handler).price([MILK])
        errors.append(raised.value)

    assert fake_api.requests[0].headers["X-API-Key"] == sentinel_key  # the one place it is sent
    for error in errors:
        shown = " ".join([str(error), repr(error), error.detail, repr(error.extensions),
                          error.to_problem().model_dump_json(), "".join(traceback.format_exception(error))])
        assert sentinel_key not in shown
        # No chained httpx error: it would carry the request, and the request carries the header.
        assert error.__cause__ is None and error.__context__ is None
    written = [path for path in live_settings.tta_data_dir.rglob("*") if path.is_file()]
    assert len(written) >= 4  # the budget file, two bodies, the manifest and the id list
    for path in written:
        assert sentinel_key not in path.read_text(encoding="utf-8"), path.name
    assert caplog.records
    for record in caplog.records:
        assert sentinel_key not in record.getMessage()
        assert sentinel_key not in repr(record.__dict__)
    assert sentinel_key not in repr(client) + repr(vars(client))


def test_an_answer_that_echoes_the_key_is_neither_recorded_nor_used(
    make_client, live_settings, sentinel_key
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        entry = {"productId": MILK, "salesBlock": False, "scheduleLines": [], "debug": sentinel_key}
        return httpx.Response(200, json={"timeNow": "2026-11-14T02:52:45+0200", "products": [entry]})

    client = make_client(handler)

    with pytest.raises(SupplierUnavailable) as raised:
        client.availability([MILK])

    assert "not recorded" in raised.value.detail
    assert not (live_settings.tta_data_dir / "recordings").exists()


def test_a_recording_holds_the_body_and_no_request_header(make_client, fake_api, live_settings) -> None:
    client = make_client(fake_api)

    client.price([MILK])

    session = next((live_settings.tta_data_dir / "recordings").iterdir())
    manifest = json.loads((session / "manifest.json").read_text(encoding="utf-8"))
    everything = " ".join(path.read_text(encoding="utf-8") for path in session.iterdir()).lower()
    assert set(manifest["requests"][0]) == {"file", "endpoint", "ids", "time_now"}
    for header in ("x-api-key", "user-agent", "authorization", "headers"):
        assert header not in everything
