"""AP-3 and the offline half of AP-7: `scripts/record_evidence.py` and `tta.evidence.batch`, with a stand-in for
Context.dev. No test here sends anything: the one real client that is built gets a transport that fails the test."""

from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import httpx
import pytest

from tta.catalog import ProductCatalog
from tta.config import REPO_ROOT, Settings
from tta.contracts.errors import SupplierUnavailable
from tta.customers.loader import shipped_customers
from tta.evidence import batch
from tta.evidence.answers import AnswerRecord, AnswersClient, EvidenceUnavailable
from tta.evidence.cache import EvidenceCache
from tta.evidence.demo_set import NAMED_CASES, demo_requests
from tta.evidence.finder import COUNT_FILE

Make = Callable[..., Any]
ALMOND_DRINK = "465793"
# Measured in replay at the recording's instant (Sat 14 Nov 2026 02:52 +02:00): the demo's products that rule P-04
# sends to a person. 469512 has a recorded page; the other eight have none.
DEMO_SET = ("462775", "463047", "463975", "464401", "464517", "464608", "465793", "469162", "469512")
RECORDED = "469512"
# All nine are recorded since 14 Nov 17:58 UTC (fixtures/evidence/), so a dry run of the demo set asks nothing.
USED_IN_AN_EMPTY_FOLDER = (
    "Requests to Context.dev: 12 used of 60 (0 recordings that carry a paid answer, 12 requests of the team's log "
    "that left no recording; the count file holds 0). 48 left."
)


class StandIn:
    """Stands for Context.dev: answers the Elovena body for every product and notes what it was sent."""

    def __init__(self, body: dict[str, Any], retrieved_at: Any, refuse: frozenset[str] = frozenset()) -> None:
        self.body, self.retrieved_at, self.refuse = body, retrieved_at, refuse
        self.sent: list[tuple[str, dict[str, Any]]] = []

    def send(self, product_id: str, body: dict[str, Any]) -> AnswerRecord:
        self.sent.append((product_id, body))
        if product_id in self.refuse:
            raise EvidenceUnavailable("the research ran out of time")
        return AnswerRecord(product_id=product_id, retrieved_at=self.retrieved_at, request=body, body=self.body)


@pytest.fixture
def script() -> Iterator[ModuleType]:
    spec = importlib.util.spec_from_file_location("tta_record_evidence", REPO_ROOT / "scripts" / "record_evidence.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["tta_record_evidence"] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop("tta_record_evidence", None)


@pytest.fixture
def run(script: ModuleType, catalog: ProductCatalog, tmp_path: Path) -> Callable[..., SimpleNamespace]:
    def call(*argv: str, sender: Any = None, settings: Settings | None = None) -> SimpleNamespace:
        lines: list[str] = []
        code = script.main(
            list(argv), settings=settings or Settings.for_tests(), catalog=catalog, sender=sender,
            directory=tmp_path / "evidence", counter=tmp_path / COUNT_FILE, out=lines.append,
        )
        return SimpleNamespace(code=code, lines=lines, text="\n".join(lines), directory=tmp_path / "evidence",
                               counter=tmp_path / COUNT_FILE)

    return call


@pytest.fixture
def stand_in(bodies: SimpleNamespace) -> StandIn:
    return StandIn(bodies.elovena, bodies.retrieved_at)


# --- the dry run --------------------------------------------------------------------------------------------------


def test_a_dry_run_prints_bodies_that_hold_the_two_names_and_the_brand_and_sends_nothing(
    run: Make, stand_in: StandIn, catalog: ProductCatalog
) -> None:
    done = run("--ids", ALMOND_DRINK, "--dry-run", sender=stand_in)

    assert done.code == 0 and stand_in.sent == []
    assert not done.directory.exists()
    body = json.loads(done.lines[2])
    assert set(body) == {"mode", "task", "json_format", "timeoutOpts"}
    assert "'Alpro Barista Almond drink 1L'" in body["task"]
    assert "Finnish name 'Alpro Barista Mantelijuoma 1L'" in body["task"] and "brand 'Alpro'" in body["task"]
    for buyer_detail in ("hotel", "school", "ward", "profile", "litres", "Monday", ALMOND_DRINK, "AN", "nuts"):
        assert buyer_detail not in body["task"].replace("Finnish", "")
    assert done.lines[1] == "465793 would be sent (100 credits):"
    assert done.lines[-2] == USED_IN_AN_EMPTY_FOLDER
    assert done.lines[-1] == (
        "Dry run: 1 request(s) would be sent to Context.dev, 100 credits each, 100 credits in all (limit 10). "
        "Nothing was sent."
    )


def test_the_demo_set_is_measured_in_replay_and_no_product_with_a_recorded_page_would_be_asked(
    script: ModuleType, catalog: ProductCatalog, tmp_path: Path
) -> None:
    lines: list[str] = []
    settings = Settings.for_tests()

    code = script.main(["--demo-set", "--dry-run"], settings=settings, catalog=catalog,
                       counter=tmp_path / COUNT_FILE, out=lines.append)

    assert code == 0  # against the repository's own fixtures/evidence/, read only
    # S17: a fresh checkout does not restart at 0. 13 recordings and the 12 requests that left none: the team's 25.
    assert lines[-2] == (
        "Requests to Context.dev: 25 used of 60 (13 recordings that carry a paid answer, 12 requests of the team's "
        "log that left no recording; the count file holds 0). 35 left."
    )
    assert f"Products with an allergen doubt on the list: {', '.join(DEMO_SET)}." in lines
    assert f"Already recorded, not asked again: {', '.join(DEMO_SET)}." in lines
    assert not [line for line in lines if line.endswith("would be sent (100 credits):")]
    assert lines[-1].startswith("Dry run: 0 request(s) would be sent to Context.dev, 100 credits each, 0 credits")


def test_the_demo_requests_are_each_customers_usual_products_and_the_named_cases() -> None:
    customers = shipped_customers()

    requests = demo_requests(customers, date(2026, 11, 16))

    usual = sum(len(customer.usual) for customer in customers.values())
    assert len(requests) == 2 * usual + len(NAMED_CASES)
    assert {profile for profile, _ in requests} == set(customers)
    assert all(len(request.lines) == 1 for _, request in requests)


# --- the cap ------------------------------------------------------------------------------------------------------


def test_the_run_never_goes_past_the_limit_it_is_given(run: Make, stand_in: StandIn) -> None:
    done = run("--ids", "462775", "463047", "463975", "--limit", "2", sender=stand_in)

    assert done.code == 0
    assert [product_id for product_id, _ in stand_in.sent] == ["462775", "463047"]
    assert "Over the limit of 2, not asked in this run: 463975." in done.lines
    assert sorted(path.name for path in done.directory.iterdir()) == ["462775.json", "463047.json"]


def test_the_default_limit_is_ten(run: Make, stand_in: StandIn, script: ModuleType) -> None:
    eleven = [product_id for product_id in DEMO_SET if product_id != RECORDED] + ["464013", "470863", "473424"]

    done = run("--ids", *eleven, sender=stand_in)

    assert script.DEFAULT_LIMIT == 10 and len(stand_in.sent) == 10
    assert "Over the limit of 10, not asked in this run: 473424." in done.lines


def test_a_limit_below_one_is_refused(run: Make, stand_in: StandIn) -> None:
    done = run("--ids", ALMOND_DRINK, "--limit", "0", sender=stand_in)

    assert (done.code, done.lines, stand_in.sent) == (2, ["--limit and --total-cap must be at least 1."], [])


def test_the_real_client_is_built_with_the_limit_as_its_own_cap(
    script: ModuleType, catalog: ProductCatalog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    bodies: SimpleNamespace,
) -> None:
    built: list[dict[str, Any]] = []
    real = AnswersClient.__init__
    counter = tmp_path / COUNT_FILE

    def noting(self: AnswersClient, settings: Settings, **options: Any) -> None:
        built.append(options)
        real(self, settings, transport=httpx.MockTransport(lambda _: httpx.Response(200, json=bodies.elovena)),
             **options)

    monkeypatch.setattr(AnswersClient, "__init__", noting)
    settings = Settings.for_tests(context_dev_api_key="ctx-test-key-not-real")
    lines: list[str] = []

    code = script.main(["--ids", ALMOND_DRINK, "--limit", "3"], settings=settings, catalog=catalog,
                       directory=tmp_path / "evidence", counter=counter, out=lines.append)

    # One product to ask on top of the 12 counted: the client may go to 13 and no further, and keeps the count.
    assert (code, built) == (0, [{"max_calls": 13, "counter": counter, "floor": 12}])
    assert json.loads(counter.read_text(encoding="utf-8")) == {"requests_sent": 13}
    assert "ctx-test-key-not-real" not in "\n".join(lines)
    assert "ctx-test-key-not-real" not in (tmp_path / "evidence" / f"{ALMOND_DRINK}.json").read_text(encoding="utf-8")


# --- a real run, with the stand-in -------------------------------------------------------------------------------


def test_a_run_writes_each_answer_in_the_format_the_gateway_replays(
    run: Make, stand_in: StandIn, catalog: ProductCatalog, ids: SimpleNamespace
) -> None:
    done = run("--ids", ids.elovena, sender=stand_in)

    stored = EvidenceCache(done.directory).get(ids.elovena)
    assert stored is not None and stored.body == stand_in.body
    assert set(json.loads((done.directory / f"{ids.elovena}.json").read_text(encoding="utf-8"))) == {
        "product_id", "retrieved_at", "endpoint", "request", "response",
    }
    assert f"{ids.elovena}: The manufacturer's page “Elovena Kaurajuoma kahviin” on elovena.fi says:" in done.text
    assert "Products asked                                               1" in done.text


def test_a_product_that_already_has_a_file_is_not_asked_again(
    run: Make, stand_in: StandIn, ids: SimpleNamespace
) -> None:
    run("--ids", ids.elovena, sender=stand_in)

    again = run("--ids", ids.elovena, sender=stand_in)

    assert len(stand_in.sent) == 1
    assert again.code == 0
    assert (again.lines[-3], again.lines[-1]) == (
        f"Already recorded, not asked again: {ids.elovena}.", "Nothing to ask. Nothing was sent.",
    )
    assert again.lines[-2].startswith("Requests to Context.dev: 13 used of 60 (1 recordings that carry a paid ")


def test_a_refusal_is_said_and_writes_no_file_and_the_run_goes_on(
    run: Make, bodies: SimpleNamespace, ids: SimpleNamespace
) -> None:
    sender = StandIn(bodies.elovena, bodies.retrieved_at, refuse=frozenset({ALMOND_DRINK}))

    done = run("--ids", ALMOND_DRINK, ids.elovena, sender=sender)

    assert done.code == 5  # S10: a partial failure is not a success
    assert done.lines[-1] == "FAILED for 1 of 2 product(s), each with its reason above: 465793."
    assert (
        "465793: No evidence was found on the web for product 465793: the research ran out of time. (no file written)"
    ) in done.lines
    assert [path.name for path in done.directory.iterdir()] == [f"{ids.elovena}.json"]
    assert "Answers received and stored                                  1" in done.text


def test_without_a_key_a_real_run_sends_nothing_and_says_so(run: Make) -> None:
    done = run("--ids", ALMOND_DRINK)

    assert done.code == 3
    assert done.lines[-1] == "No Context.dev key is set (CONTEXT_DEV_API_KEY), so nothing was sent."
    assert not done.directory.exists()


def test_an_id_that_is_no_product_is_named_and_not_asked(run: Make, stand_in: StandIn) -> None:
    done = run("--ids", "../../etc/passwd", "999999999", sender=stand_in)

    assert stand_in.sent == []
    assert "Not in the catalog, not asked: ../../etc/passwd, 999999999." in done.lines


# --- the summary --------------------------------------------------------------------------------------------------


def test_the_summary_counts_asked_found_matched_dropped_and_naming_an_allergen(
    catalog: ProductCatalog, bodies: SimpleNamespace, ids: SimpleNamespace, tmp_path: Path, record: Make
) -> None:
    cache = EvidenceCache(tmp_path)
    results = {
        ids.elovena: record(ids.elovena, bodies.elovena).to_json(),  # matched, names oats
        ids.oddlygood_oat: record(ids.oddlygood_oat, bodies.wrong_product).to_json(),  # another product's page
        ids.oddlygood_almond: record(ids.oddlygood_almond, bodies.not_found).to_json(),  # no page
        ALMOND_DRINK: {"product_id": ALMOND_DRINK, "unavailable": "the research ran out of time"},
        "463047": {"anything": "else"},  # not a record
    }

    outcomes = [batch.keep(result, catalog.get_product(pid), cache) for pid, result in results.items()]
    summary = batch.summarise(outcomes)

    assert (summary.asked, summary.answered, summary.page_found, summary.matched, summary.dropped,
            summary.names_an_allergen, summary.credits) == (5, 3, 2, 1, 1, 1, 300)
    assert batch.recorded_ids(tmp_path) == {ids.elovena, ids.oddlygood_oat, ids.oddlygood_almond}
    assert outcomes[4].evidence.sentence.endswith(": the answer could not be read.")
    # S10: what came back and could not be read is kept as it came, where nothing replays it.
    assert json.loads((tmp_path / "unreadable" / "463047.json").read_text(encoding="utf-8")) == {
        "product_id": "463047", "received": {"anything": "else"},
    }


def test_an_answer_for_another_product_than_the_one_asked_is_not_kept(
    catalog: ProductCatalog, bodies: SimpleNamespace, ids: SimpleNamespace, tmp_path: Path, record: Make
) -> None:
    outcome = batch.keep(record(ids.elovena, bodies.elovena).to_json(), catalog.get_product(ALMOND_DRINK),
                         EvidenceCache(tmp_path))

    assert outcome.record is None and not outcome.evidence.found
    assert batch.recorded_ids(tmp_path) == frozenset()


def test_a_batch_that_answers_another_number_of_results_is_refused(
    catalog: ProductCatalog, tmp_path: Path
) -> None:
    planned = batch.plan([ALMOND_DRINK], catalog, frozenset(), 5)

    with pytest.raises(ValueError, match="another number of results"):
        batch.record(planned, EvidenceCache(tmp_path), lambda calls: [])


def test_products_whose_data_states_nothing_are_picked_from_a_list(catalog: ProductCatalog) -> None:
    # 464517 and 464608 (AIMO yoghurts) hold no allergen statement; 465793 holds several.
    assert batch.stating_nothing(["464517", ALMOND_DRINK, "464608", "999999999", "464517"], catalog) == (
        "464517", "464608",
    )


# --- S10: the exit status, the reasons, and an answer that was paid for and cannot be read ---------------------------


def test_a_run_in_which_nothing_was_answered_exits_with_its_own_status(
    run: Make, bodies: SimpleNamespace, ids: SimpleNamespace
) -> None:
    sender = StandIn(bodies.elovena, bodies.retrieved_at, refuse=frozenset({ALMOND_DRINK, ids.elovena}))

    done = run("--ids", ALMOND_DRINK, ids.elovena, sender=sender)

    assert done.code == 4
    assert done.lines[-1] == "FAILED: none of the 2 product(s) asked was answered."
    assert sum("the research ran out of time. (no file written)" in line for line in done.lines) == 2


def test_an_answer_that_was_received_and_cannot_be_read_is_stored_as_it_came(
    script: ModuleType, catalog: ProductCatalog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = AnswersClient.__init__

    def with_transport(self: AnswersClient, settings: Settings, **options: Any) -> None:
        real(self, settings, transport=httpx.MockTransport(lambda _: httpx.Response(200, text="<html>paid</html>")),
             **options)

    monkeypatch.setattr(AnswersClient, "__init__", with_transport)
    lines: list[str] = []

    code = script.main(
        ["--ids", ALMOND_DRINK], settings=Settings.for_tests(context_dev_api_key="ctx-test-key-not-real"),
        catalog=catalog, directory=tmp_path / "evidence", counter=tmp_path / COUNT_FILE, out=lines.append,
    )

    kept = tmp_path / "evidence" / "unreadable" / f"{ALMOND_DRINK}.json"
    assert code == 4
    assert json.loads(kept.read_text(encoding="utf-8")) == {"product_id": ALMOND_DRINK, "received": "<html>paid</html>"}
    assert (
        "465793: No evidence was found on the web for product 465793: the answer could not be read. (no recording "
        "written; what was received is kept in evidence/unreadable/465793.json, and a new run would ask and pay again)"
    ) in lines
    assert batch.recorded_ids(tmp_path / "evidence") == frozenset()  # never replayed as a recording
    assert "ctx-test-key-not-real" not in kept.read_text(encoding="utf-8")


def test_a_refusal_carries_no_raw_text_and_stores_nothing(tmp_path: Path, catalog: ProductCatalog) -> None:
    client = AnswersClient(
        Settings.for_tests(context_dev_api_key="ctx-test-key-not-real"),
        transport=httpx.MockTransport(lambda _: httpx.Response(402, text="pay up")),
    )

    with pytest.raises(EvidenceUnavailable) as refused:
        client.ask(catalog.get_product(ALMOND_DRINK))
    result = batch.ask_one(batch.payload(catalog.get_product(ALMOND_DRINK)), client)
    outcome = batch.keep(result, catalog.get_product(ALMOND_DRINK), EvidenceCache(tmp_path))

    assert refused.value.raw is None and "raw" not in result
    assert outcome.failed and outcome.raw_kept is None and not list(tmp_path.iterdir())


def test_an_offer_of_the_demo_set_that_cannot_be_built_is_named_counted_and_in_the_exit_status(
    script: ModuleType, catalog: ProductCatalog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = script.OfferService.build_offer
    calls: list[int] = []

    def failing_once(self: Any, request: Any, agent: Any) -> Any:
        calls.append(1)
        if len(calls) == 1:
            raise SupplierUnavailable("the supplier did not answer")
        return real(self, request, agent)

    monkeypatch.setattr(script.OfferService, "build_offer", failing_once)
    lines: list[str] = []

    code = script.main(["--demo-set", "--dry-run"], settings=Settings.for_tests(), catalog=catalog,
                       counter=tmp_path / COUNT_FILE, out=lines.append)

    assert code == 6
    skipped = [line for line in lines if line.startswith("No offer for ")]
    assert len(skipped) == 1 and skipped[0].endswith("SupplierUnavailable: the supplier did not answer. Skipped.")
    assert "1 offer(s) could not be built: the list below may miss the products they would have added." in lines


# --- S17: the team's total, across runs -----------------------------------------------------------------------------


def test_the_total_cap_bounds_a_run_below_its_limit(run: Make, stand_in: StandIn) -> None:
    done = run("--ids", "462775", "463047", "463975", "--total-cap", "14", sender=stand_in)  # 12 are counted

    assert [product_id for product_id, _ in stand_in.sent] == ["462775", "463047"]
    assert "Over the limit of 2, not asked in this run: 463975." in done.lines
    assert any(line.startswith("Requests to Context.dev: 12 used of 14 ") for line in done.lines)


@pytest.mark.parametrize("dry_run", [(), ("--dry-run",)])
def test_a_spent_total_sends_nothing_and_exits_with_its_own_status(
    run: Make, stand_in: StandIn, dry_run: tuple[str, ...]
) -> None:
    done = run("--ids", ALMOND_DRINK, "--total-cap", "12", *dry_run, sender=stand_in)

    assert (done.code, stand_in.sent) == (7, [])
    assert done.lines[-1].startswith("The total is spent: nothing can be sent.")


def test_the_count_file_is_used_when_it_holds_more_than_the_floor_and_deleting_it_does_not_restart_at_zero(
    run: Make, stand_in: StandIn, tmp_path: Path
) -> None:
    (tmp_path / COUNT_FILE).write_text('{"requests_sent": 58}', encoding="utf-8")

    counted = run("--ids", "462775", "463047", "463975", "--dry-run", sender=stand_in)
    (tmp_path / COUNT_FILE).unlink()
    deleted = run("--ids", "462775", "--dry-run", sender=stand_in)

    assert counted.lines[-2].startswith("Requests to Context.dev: 58 used of 60 ")
    assert counted.lines[-1].startswith("Dry run: 2 request(s) would be sent")
    assert deleted.lines[-2] == USED_IN_AN_EMPTY_FOLDER


def test_a_count_file_that_cannot_be_read_sends_nothing(run: Make, stand_in: StandIn, tmp_path: Path) -> None:
    (tmp_path / COUNT_FILE).write_text("{", encoding="utf-8")

    done = run("--ids", ALMOND_DRINK, sender=stand_in)

    assert (done.code, stand_in.sent) == (8, [])
    assert done.lines[0].startswith(
        "Nothing was sent: the count of web lookups already made could not be read, so none was made ("
    )


def test_the_floor_counts_the_recordings_that_carry_a_paid_answer(
    tmp_path: Path, bodies: SimpleNamespace, record: Make
) -> None:
    cache = EvidenceCache(tmp_path)
    free = {**bodies.elovena, "key_metadata": {"credits_consumed": 0}}
    cache.put(record("469512", bodies.elovena))  # 100 credits
    cache.put(record("468465", free))  # says it cost nothing
    cache.put(record("474864", {"json_content": {}}))  # no word on credits: counted
    (tmp_path / "475224.json").write_text("{", encoding="utf-8")  # cannot be read: counted
    (tmp_path / COUNT_FILE).write_text('{"requests_sent": 1}', encoding="utf-8")  # no product id: no recording

    used = batch.requests_used(tmp_path, tmp_path / COUNT_FILE)

    assert (used.recordings, used.stored, used.floor, used.total) == (3, 1, 3 + batch.UNRECORDED_REQUESTS, 15)
    assert (batch.DEFAULT_TOTAL_CAP, batch.UNRECORDED_REQUESTS) == (60, 12)


def test_a_client_with_a_floor_never_counts_below_it(
    tmp_path: Path, catalog: ProductCatalog, bodies: SimpleNamespace
) -> None:
    client = AnswersClient(
        Settings.for_tests(context_dev_api_key="ctx-test-key-not-real"), max_calls=26, floor=25,
        counter=tmp_path / COUNT_FILE,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=bodies.elovena)),
    )

    assert client.calls_made == 25
    client.ask(catalog.get_product(ALMOND_DRINK))
    with pytest.raises(EvidenceUnavailable, match="limit of 26 web lookups is spent"):
        client.ask(catalog.get_product(ALMOND_DRINK))
    assert json.loads((tmp_path / COUNT_FILE).read_text(encoding="utf-8")) == {"requests_sent": 26}
