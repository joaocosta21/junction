"""Replay answers from a capture folder exactly as the live client would from the same bodies (SPEC section 10)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tta.contracts.common import DataSource
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.ports import Clock, ValioGateway
from tta.valio import ReplayGateway

UNKNOWN_ID = "000000"  # in no capture and not in the catalog
TIME_NOW = "2026-11-14T02:52:45+0200"


def write_capture(folder: Path, manifest: Any, files: dict[str, str] | None = None) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    for name, text in (files or {}).items():
        (folder / name).write_text(text, encoding="utf-8")
    return folder


def test_replay_satisfies_the_gateway_port_and_says_it_is_a_replay(capture_demo) -> None:
    replay = ReplayGateway(capture_demo.path)

    assert isinstance(replay, ValioGateway)
    assert isinstance(replay.clock, Clock)
    assert replay.source is DataSource.REPLAY
    assert replay.price(["464306"]).source is DataSource.REPLAY
    assert replay.availability(["464306"]).source is DataSource.REPLAY


def test_replay_pins_every_time_to_the_capture(capture_demo) -> None:
    replay = ReplayGateway(capture_demo.path)

    assert replay.time_now == capture_demo.time_now
    assert replay.clock.now() == capture_demo.time_now
    assert replay.availability(["464306"]).time_now == capture_demo.time_now
    assert replay.price(["464306"]).retrieved_at == capture_demo.time_now


def test_replay_reads_the_capture_named_in_the_settings(settings) -> None:
    replay = ReplayGateway(settings.replay_capture_dir)

    assert replay.price(["469363"]).by_id()["469363"].has_price


@pytest.mark.parametrize("capture_name", ["2026-11-14-demo", "2026-11-13-sample", "2026-11-13-extras"])
def test_replay_equals_parsing_the_same_bodies_live(load_capture, make_api, make_client, capture_name: str) -> None:
    capture = load_capture(capture_name)
    client = make_client(make_api(capture))
    replay = ReplayGateway(capture.path)
    ids = [*capture.ids, UNKNOWN_ID]

    live_price = client.price(ids)
    live_availability = client.availability(ids)
    replayed_price = replay.price(ids)
    replayed_availability = replay.availability(ids)

    assert replayed_price.lines == live_price.lines
    assert replayed_availability.lines == live_availability.lines
    # Apart from the stated source (and when the price was fetched) the answers are the same objects.
    assert replayed_availability == live_availability.model_copy(update={"source": DataSource.REPLAY})
    assert replayed_price == live_price.model_copy(
        update={"source": DataSource.REPLAY, "retrieved_at": replayed_price.retrieved_at}
    )


def test_an_id_the_capture_does_not_hold_reads_like_an_unknown_id_on_the_live_api(capture_sample) -> None:
    replay = ReplayGateway(capture_sample.path)

    price = replay.price([UNKNOWN_ID]).lines[0]
    availability = replay.availability([UNKNOWN_ID]).lines[0]

    # 459999 is the made-up id the live API was asked for on Friday (AIMO/docs/API.md section 8.5).
    recorded_price = replay.price(["459999"]).lines[0]
    recorded_availability = replay.availability(["459999"]).lines[0]
    assert price == recorded_price.model_copy(update={"product_id": UNKNOWN_ID})
    assert availability == recorded_availability.model_copy(update={"product_id": UNKNOWN_ID})
    assert price.error is True and not price.has_price
    assert availability.schedule_line is None and availability.sales_block is False


def test_replay_answers_in_the_order_asked_and_once_per_id(capture_demo) -> None:
    replay = ReplayGateway(capture_demo.path)

    response = replay.availability(["469363", "464306", "469363"])

    assert [line.product_id for line in response.lines] == ["469363", "464306"]


def test_replay_with_no_ids_answers_empty(capture_demo) -> None:
    replay = ReplayGateway(capture_demo.path)

    assert replay.price([]).lines == ()
    assert replay.availability([]).lines == ()


def test_a_single_string_is_not_taken_for_a_list_of_ids(capture_demo) -> None:
    replay = ReplayGateway(capture_demo.path)

    with pytest.raises(TypeError):
        replay.availability("464306")


def test_a_capture_that_is_not_there_is_reported_with_the_typed_error(tmp_path: Path) -> None:
    with pytest.raises(SupplierUnavailable) as raised:
        ReplayGateway(tmp_path / "no-such-capture")

    assert "no-such-capture" in raised.value.detail


@pytest.mark.parametrize(
    "manifest",
    [
        ["not", "an", "object"],
        {"files": {"availability": [], "price": []}},
        {"time_now": "2026-11-14T02:52:45", "files": {"availability": [], "price": []}},
        {"time_now": TIME_NOW},
        {"time_now": TIME_NOW, "files": {"availability": "availability-1.json", "price": []}},
        {"time_now": TIME_NOW, "files": {"availability": ["../outside.json"], "price": []}},
        {"time_now": TIME_NOW, "files": {"availability": ["/etc/hosts"], "price": []}},
        {"time_now": TIME_NOW, "files": {"availability": ["missing.json"], "price": []}},
        {"time_now": TIME_NOW, "files": {"availability": [7], "price": []}},
    ],
)
def test_a_manifest_that_cannot_be_trusted_is_refused(tmp_path: Path, manifest: Any) -> None:
    (tmp_path / "outside.json").write_text('{"timeNow": "2026-11-14T02:52:45+0200", "products": []}', encoding="utf-8")
    folder = write_capture(tmp_path / "capture", manifest)

    with pytest.raises(SupplierUnavailable):
        ReplayGateway(folder)


def test_a_manifest_that_is_not_json_is_refused(tmp_path: Path) -> None:
    folder = tmp_path / "capture"
    folder.mkdir()
    (folder / "manifest.json").write_text("time_now: yesterday", encoding="utf-8")

    with pytest.raises(SupplierUnavailable) as raised:
        ReplayGateway(folder)

    assert "manifest.json" in raised.value.detail


def test_a_capture_with_a_broken_body_is_refused(tmp_path: Path) -> None:
    manifest = {"time_now": TIME_NOW, "files": {"availability": ["availability-1.json"], "price": []}}
    folder = write_capture(tmp_path / "capture", manifest, {"availability-1.json": "<html>not json</html>"})

    with pytest.raises(SupplierUnavailable):
        ReplayGateway(folder)


def test_a_capture_with_availability_only_still_answers_prices_as_unknown(tmp_path: Path) -> None:
    body = {"timeNow": TIME_NOW, "products": [{"productId": "1", "salesBlock": False, "scheduleLines": []}]}
    manifest = {"time_now": TIME_NOW, "files": {"availability": ["availability-1.json"], "price": []}}
    folder = write_capture(tmp_path / "capture", manifest, {"availability-1.json": json.dumps(body)})

    replay = ReplayGateway(folder)

    assert replay.price(["1"]).lines[0].error is True
    assert replay.availability(["1"]).lines[0].product_id == "1"
