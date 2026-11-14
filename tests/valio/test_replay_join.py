"""Two recordings of the same Saturday read as one (task CK).

`2026-11-14-demo` (769 products, 02:52) gives the clock and wins wherever both hold a product; its manifest joins
`2026-11-14-baking` (394 baking products, recorded at 21:12). Valio Aimo said on 14 Nov 2026 that its test data is
static, which is why joining two recordings of the same Saturday is honest. No answer is silently taken from the
later time: the gateway says which recording answered a product and when that recording was made.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from tta.contracts.common import ClockBasis
from tta.contracts.errors import SupplierUnavailable
from tta.valio import ReplayGateway
from tta.valio.replay import JOINED_KEY

BAKING = "2026-11-14-baking"
EARLY = "2026-11-14T02:52:45+0200"
LATE = "2026-11-14T21:12:02+0200"
BUTTER_IDS = ("464205", "476731")  # two Valio butters of category 10500: in the baking recording only
UNKNOWN_ID = "000000"


def _manifest_without_join(capture: Any) -> dict[str, Any]:
    return {key: value for key, value in capture.manifest.items() if key != JOINED_KEY}


def _copy_alone(capture: Any, folder: Path) -> Path:
    """The demo recording as it was before the join: the same body files, no joined recording."""
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_text(json.dumps(_manifest_without_join(capture)), encoding="utf-8")
    for names in capture.manifest["files"].values():
        for name in names:
            (folder / name).write_bytes((capture.path / name).read_bytes())
    return folder


def _body(endpoint: str, time_now: str, entries: list[dict[str, Any]], requested: str = "2026-11-16") -> str:
    if endpoint == "price":
        head = {"customerId": "123", "currency": "EUR", "pricingDate": f"{requested}T00:00:00+0200"}
    else:
        head = {"timeNow": time_now, "requestedDate": f"{requested}T00:00:00+0200"}
    return json.dumps({**head, "products": entries})


def _line(product_id: str, amount: int) -> dict[str, Any]:
    schedule = {"salesBlock": False, "availableAmount": amount, "availableDate": "2026-11-16", "salesUnit": "KPL"}
    return {"productId": product_id, "salesBlock": False, "logisticModel": "Stock", "scheduleLines": [schedule]}


def _recording(root: Path, name: str, time_now: str, amounts: dict[str, int], **manifest: Any) -> Path:
    folder = root / name
    folder.mkdir(parents=True)
    body = _body("availability", time_now, [_line(pid, amount) for pid, amount in amounts.items()])
    (folder / "availability-1.json").write_text(body, encoding="utf-8")
    listed = {"time_now": time_now, "files": {"availability": ["availability-1.json"], "price": []}, **manifest}
    (folder / "manifest.json").write_text(json.dumps(listed), encoding="utf-8")
    return folder


def test_the_demo_recording_joins_the_baking_recording_and_keeps_its_own_clock(capture_demo, load_capture) -> None:
    baking = load_capture(BAKING)
    replay = ReplayGateway(capture_demo.path)

    assert capture_demo.manifest[JOINED_KEY] == [BAKING]
    assert replay.time_now == replay.recorded_at == capture_demo.time_now == datetime.fromisoformat(EARLY)
    assert replay.time_basis is ClockBasis.RECORDING
    assert replay.product_count == 769 + 394 == 1163
    assert [(each.name, each.recorded_at, each.product_count) for each in replay.later_recordings] == [
        (BAKING, baking.time_now, 394)
    ]
    assert not set(capture_demo.ids) & set(baking.ids)  # counted on 14 Nov: no product is in both


def test_every_demo_product_answers_exactly_as_before_the_join(capture_demo, tmp_path: Path) -> None:
    alone = ReplayGateway(_copy_alone(capture_demo, tmp_path / capture_demo.name))
    joined = ReplayGateway(capture_demo.path)
    ids = list(capture_demo.ids)

    assert alone.later_recordings == () and alone.product_count == 769
    assert joined.availability(ids).model_dump_json() == alone.availability(ids).model_dump_json()
    assert joined.price(ids).model_dump_json() == alone.price(ids).model_dump_json()
    assert {joined.recording_of(product_id) for product_id in ids} == {capture_demo.name}
    assert {joined.recorded_at_of(product_id) for product_id in ids} == {capture_demo.time_now}


def test_the_demo_recordings_own_files_are_untouched_by_the_join(capture_demo) -> None:
    """The join is one key of the manifest: the count, the clock and the list of body files are as recorded."""
    assert capture_demo.manifest["product_count"] == 769 == len(capture_demo.ids)
    assert capture_demo.manifest["time_now"] == EARLY
    assert capture_demo.manifest["files"] == {"availability": ["availability-1.json"], "price": ["price-1.json"]}
    assert "static" in capture_demo.manifest["joined_note"] and "21:12" in capture_demo.manifest["joined_note"]


def test_a_baking_product_answers_from_the_later_recording_and_says_so(capture_demo, load_capture) -> None:
    baking = load_capture(BAKING)
    joined, own = ReplayGateway(capture_demo.path), ReplayGateway(baking.path)

    availability = joined.availability(BUTTER_IDS)
    assert availability.lines == own.availability(BUTTER_IDS).lines
    assert joined.price(BUTTER_IDS).lines == own.price(BUTTER_IDS).lines
    assert not any(line.not_in_recording for line in availability.lines)
    assert availability.time_now == capture_demo.time_now  # the first recording gives the clock
    for product_id in BUTTER_IDS:
        assert joined.recording_of(product_id) == BAKING
        assert joined.recorded_at_of(product_id) == datetime.fromisoformat(LATE)
    assert joined.recorded_later(["469363", *BUTTER_IDS, UNKNOWN_ID]) == BUTTER_IDS


def test_the_join_is_said_in_one_sentence_with_both_instants_and_valios_answer(capture_demo) -> None:
    sentence = ReplayGateway(capture_demo.path).join_sentence

    assert sentence == (
        "394 of the 1,163 recorded products were recorded later than the rest: on Saturday 14 Nov at 21:12 "
        "(recording 2026-11-14-baking), against Saturday 14 Nov at 02:52 for the other 769 (recording "
        "2026-11-14-demo, which gives the clock). Valio Aimo said on 14 Nov 2026 that its test data is static, "
        "which is why two recordings of the same Saturday are read as one."
    )


def test_a_recording_with_no_join_has_no_sentence_and_no_later_product(capture_sample) -> None:
    replay = ReplayGateway(capture_sample.path)

    assert replay.join_sentence is None and replay.later_recordings == ()
    assert replay.recorded_later(capture_sample.ids[:5]) == ()
    assert replay.recording_of(UNKNOWN_ID) is None and replay.recorded_at_of(UNKNOWN_ID) is None


def test_a_product_outside_both_recordings_is_still_marked_not_in_the_recording(capture_demo) -> None:
    replay = ReplayGateway(capture_demo.path)

    assert replay.availability([UNKNOWN_ID]).lines[0].not_in_recording
    assert replay.price([UNKNOWN_ID]).lines[0].not_in_recording


def test_where_both_recordings_hold_a_product_the_first_wins(tmp_path: Path) -> None:
    _recording(tmp_path, "later", LATE, {"1": 5, "2": 7})
    first = _recording(tmp_path, "first", EARLY, {"1": 3}, **{JOINED_KEY: ["later"]})

    replay = ReplayGateway(first)

    amounts = {line.product_id: line.schedule_line.available_amount for line in replay.availability(["1", "2"]).lines}
    assert amounts == {"1": 3, "2": 7}
    assert (replay.recording_of("1"), replay.recording_of("2")) == ("first", "later")
    assert replay.later_recordings[0].product_count == 1 and replay.product_count == 2


def test_a_demo_clock_moves_the_clock_of_the_joined_products_too(capture_demo) -> None:
    thursday = datetime.fromisoformat("2026-11-12T14:15:00+02:00")
    recorded, moved = ReplayGateway(capture_demo.path), ReplayGateway(capture_demo.path, demo_clock=thursday)

    assert moved.availability(BUTTER_IDS).time_now == thursday
    assert moved.availability(BUTTER_IDS).lines == recorded.availability(BUTTER_IDS).lines
    assert moved.recorded_at_of(BUTTER_IDS[0]) == datetime.fromisoformat(LATE)


@pytest.mark.parametrize("joined", ["later", ["../later"], ["/etc"], [7], [""], ["first"], ["missing"]])
def test_a_join_that_cannot_be_trusted_is_refused(tmp_path: Path, joined: Any) -> None:
    _recording(tmp_path, "later", LATE, {"2": 7})
    first = _recording(tmp_path, "first", EARLY, {"1": 3}, **{JOINED_KEY: joined})

    with pytest.raises(SupplierUnavailable):
        ReplayGateway(first)


def test_a_joined_recording_of_another_requested_date_is_refused(tmp_path: Path) -> None:
    """A stock figure for Tuesday is not an answer for Monday: such a recording is never read as the same one."""
    later = _recording(tmp_path, "later", LATE, {"2": 7})
    (later / "availability-1.json").write_text(_body("availability", LATE, [_line("2", 7)], "2026-11-17"), "utf-8")
    first = _recording(tmp_path, "first", EARLY, {"1": 3}, **{JOINED_KEY: ["later"]})

    with pytest.raises(SupplierUnavailable) as raised:
        ReplayGateway(first)

    assert "requested date" in raised.value.detail


def test_a_joined_recording_does_not_join_further(tmp_path: Path) -> None:
    _recording(tmp_path, "third", LATE, {"3": 9})
    _recording(tmp_path, "later", LATE, {"2": 7}, **{JOINED_KEY: ["third"]})
    first = _recording(tmp_path, "first", EARLY, {"1": 3}, **{JOINED_KEY: ["later"]})

    replay = ReplayGateway(first)

    assert replay.product_count == 2 and replay.availability(["3"]).lines[0].not_in_recording
