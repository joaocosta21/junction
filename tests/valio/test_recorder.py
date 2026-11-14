"""Every live answer is written to `var/recordings/` in the capture format, so it can be replayed (SPEC 10)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import httpx
import pytest

from tta.contracts.errors import SupplierUnavailable
from tta.valio import Recorder, ReplayGateway

MILK = "464306"
OTHER_MILK = "469363"


def recording_sessions(data_dir: Path) -> list[Path]:
    return sorted((data_dir / "recordings").iterdir())


def test_every_live_body_is_recorded_with_its_ids_and_time_now(
    make_client, fake_api, live_settings, capture_demo
) -> None:
    client = make_client(fake_api)

    client.availability([MILK, OTHER_MILK])
    client.price([MILK])

    (session,) = recording_sessions(live_settings.tta_data_dir)
    manifest = json.loads((session / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["files"] == {"availability": ["availability-1.json"], "price": ["price-1.json"]}
    assert manifest["calls"] == 2
    assert manifest["product_count"] == 2
    assert datetime.fromisoformat(manifest["time_now"]) >= capture_demo.time_now
    assert [(entry["endpoint"], entry["ids"]) for entry in manifest["requests"]] == [
        ("availability", [MILK, OTHER_MILK]), ("price", [MILK]),
    ]
    assert datetime.fromisoformat(manifest["requests"][0]["time_now"]) == capture_demo.time_now
    # The body is kept exactly as the API returned it.
    assert (session / "availability-1.json").read_text(encoding="utf-8") == fake_api.texts[0]
    assert (session / "price-1.json").read_text(encoding="utf-8") == fake_api.texts[1]
    assert json.loads((session / "ids.json").read_text(encoding="utf-8")) == [MILK, OTHER_MILK]


def test_each_chunk_of_a_large_call_gets_its_own_file(make_client, fake_api, live_settings) -> None:
    client = make_client(fake_api)

    client.price([str(900_000 + number) for number in range(1_001)])

    (session,) = recording_sessions(live_settings.tta_data_dir)
    manifest = json.loads((session / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["files"]["price"] == ["price-1.json", "price-2.json"]
    assert [len(entry["ids"]) for entry in manifest["requests"]] == [1_000, 1]


def test_an_answer_from_the_cache_is_not_recorded_twice(make_client, fake_api, live_settings) -> None:
    client = make_client(fake_api)

    client.price([MILK])
    client.price([MILK])

    (session,) = recording_sessions(live_settings.tta_data_dir)
    assert sorted(path.name for path in session.iterdir()) == ["ids.json", "manifest.json", "price-1.json"]


def test_a_failed_call_records_nothing(make_client, live_settings) -> None:
    client = make_client(lambda request: httpx.Response(403, text="blocked"))

    with pytest.raises(SupplierUnavailable):
        client.price([MILK])

    assert not (live_settings.tta_data_dir / "recordings").exists()


def test_a_recording_can_be_replayed(make_client, fake_api, live_settings) -> None:
    client = make_client(fake_api)
    ids = [MILK, OTHER_MILK, "471881", "462199", "460032"]
    live_availability = client.availability(ids)
    live_price = client.price(ids)
    (session,) = recording_sessions(live_settings.tta_data_dir)

    replay = ReplayGateway(session)

    assert replay.availability(ids).lines == live_availability.lines
    assert replay.price(ids).lines == live_price.lines
    assert replay.clock.now() >= live_availability.time_now


def test_an_answer_that_cannot_be_recorded_is_not_handed_out(make_client, fake_api, live_settings) -> None:
    live_settings.tta_data_dir.mkdir(parents=True)
    (live_settings.tta_data_dir / "recordings").write_text("a file where the folder should be", encoding="utf-8")
    client = make_client(fake_api)

    with pytest.raises(SupplierUnavailable) as raised:
        client.price([MILK])

    assert "recorded" in raised.value.detail


def test_two_clients_started_in_the_same_second_record_to_separate_folders(
    make_client, fake_api, live_settings
) -> None:
    make_client(fake_api).price([MILK])
    make_client(fake_api).price([OTHER_MILK])

    first, second = recording_sessions(live_settings.tta_data_dir)
    assert json.loads((first / "ids.json").read_text(encoding="utf-8")) == [MILK]
    assert json.loads((second / "ids.json").read_text(encoding="utf-8")) == [OTHER_MILK]


def test_the_recorder_keeps_the_latest_time_now_and_the_union_of_ids(tmp_path: Path) -> None:
    recorder = Recorder(tmp_path / "recordings", session="session-1")
    earlier = datetime.fromisoformat("2026-11-14T02:52:45+02:00")
    later = datetime.fromisoformat("2026-11-14T02:53:10+02:00")

    recorder.record("availability", ["2", "1"], '{"products": []}', later)
    recorder.record("price", ["3"], '{"products": []}', earlier)

    manifest = json.loads((recorder.session_dir / "manifest.json").read_text(encoding="utf-8"))
    assert recorder.session_dir == tmp_path / "recordings" / "session-1"
    assert datetime.fromisoformat(manifest["time_now"]) == later
    assert manifest["capture"] == "session-1"
    assert json.loads((recorder.session_dir / "ids.json").read_text(encoding="utf-8")) == ["1", "2", "3"]
