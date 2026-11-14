"""Recording manufacturers' pages for many products: which to ask, at what cost, and what came back (AP-3, AP-7).

Scores on the 15% exceptions (missing allergen data, beyond one demo product) and gives the Context.dev note its
measured line. Nothing here sends a request by itself: `plan` and `dry_run_lines` only read, `record` asks the
source it is given (the Context.dev client, or a stand-in in a test), and `ask_one` is the body of the Modal
function of `deploy/evidence_batch.py`, one request per call.

A request holds the product's English name, its Finnish name and its brand (`answers.answer_request`), nothing
about a buyer. Each costs `CREDITS_PER_REQUEST` credits, a repeated one as much as a first one, so a product that
already has a recorded or stored answer is never asked again, and the limit a caller gives is never passed.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from tta.contracts.common import JsonDict
from tta.contracts.order import Evidence
from tta.contracts.ports import Catalog
from tta.contracts.product import Product
from tta.evidence import wording
from tta.evidence.answers import (
    CREDITS_PER_REQUEST,
    AnswerRecord,
    EvidenceUnavailable,
    answer_request,
    store_count,
    stored_count,
)
from tta.evidence.cache import PRODUCT_ID, SUFFIX, EvidenceCache
from tta.evidence.reading import read_answer

MAX_AT_ONCE = 40  # Context.dev's brief: "max 50 concurrent requests per organisation"; we stay under it
DEFAULT_BATCH_LIMIT = 40
UNAVAILABLE_KEY = "unavailable"
RAW_KEY = "raw"  # beside `unavailable`: the text of an answer that was received and could not be read
UNREADABLE_FOLDER = "unreadable"  # under the recordings; no file in it is ever replayed
# The requests the team approved in all (docs/CONTEXTDEV.md, "25 requests in all, of the 60 the team approved").
DEFAULT_TOTAL_CAP = 60
# Requests of the team's log that left no recording: 10 trials by hand and 2 refused with 401 (docs/CONTEXTDEV.md,
# 14 Nov). With the 13 recordings of that day they make the 25 the log counts.
UNRECORDED_REQUESTS = 12
CREDITS_KEY = "credits_consumed"
CAPTURE_IDS_FILE = "ids.json"  # the ids of a replay capture (AGENT-RULES.md, capture format)
_NO_MORE = object()


class BodySender(Protocol):
    """What sends one prepared body: `AnswersClient.send`, or a stand-in in a test."""

    def send(self, product_id: str, body: JsonDict) -> AnswerRecord: ...


@dataclass(frozen=True)
class Plan:
    """What a run would do, before anything is sent."""

    to_ask: tuple[Product, ...]
    already_recorded: tuple[str, ...]
    not_in_catalog: tuple[str, ...]
    over_the_limit: tuple[str, ...]
    limit: int

    @property
    def credits(self) -> int:
        return len(self.to_ask) * CREDITS_PER_REQUEST


@dataclass(frozen=True)
class Outcome:
    """One product of a run: the answer as it was received (when one was), and how it reads."""

    product_id: str
    record: AnswerRecord | None
    evidence: Evidence

    raw_kept: Path | None = None  # where an answer that could not be read was stored, as it was received

    @property
    def page_found(self) -> bool:
        content = self.record.body.get("json_content") if self.record else None
        return isinstance(content, dict) and content.get("page_found") is True

    @property
    def failed(self) -> bool:
        """True when no answer that can be replayed was stored for the product."""
        return self.record is None


@dataclass(frozen=True)
class Used:
    """The requests counted so far, and what the count rests on (S17)."""

    recordings: int  # recordings that carry a paid answer
    stored: int  # the count file's figure; 0 without a file

    @property
    def floor(self) -> int:
        return self.recordings + UNRECORDED_REQUESTS

    @property
    def total(self) -> int:
        return max(self.stored, self.floor)


@dataclass(frozen=True)
class Summary:
    asked: int
    answered: int
    page_found: int
    matched: int
    dropped: int
    names_an_allergen: int

    @property
    def credits(self) -> int:
        return self.answered * CREDITS_PER_REQUEST


def recorded_ids(directory: Path) -> frozenset[str]:
    """The product ids that have an answer file in `directory`."""
    if not directory.is_dir():
        return frozenset()
    return frozenset(path.stem for path in directory.glob(f"*{SUFFIX}") if PRODUCT_ID.fullmatch(path.stem))


def paid_recordings(directory: Path) -> int:
    """The recordings in `directory` that carry a paid answer: every answer file, except one whose response says
    it consumed 0 credits. A file that cannot be read is counted: an answer was written there."""
    paid = 0
    for product_id in recorded_ids(directory):
        try:
            data = json.loads((directory / f"{product_id}{SUFFIX}").read_text(encoding="utf-8"))
            consumed = data["response"]["key_metadata"][CREDITS_KEY]
        except (OSError, ValueError, KeyError, TypeError):
            consumed = None
        paid += 0 if consumed == 0 and not isinstance(consumed, bool) else 1
    return paid


def requests_used(directory: Path, counter: Path | None) -> Used:
    """How many requests count against the team's total. The count file is one machine's memory and is not in the
    repository, so a fresh checkout or a deleted file would restart at 0; the floor does not: the recordings that
    carry a paid answer, plus the `UNRECORDED_REQUESTS` of the team's log. The larger of the two is used. Raises
    `EvidenceUnavailable` for a count file that cannot be read."""
    return Used(recordings=paid_recordings(directory), stored=stored_count(counter))


def used_line(used: Used, total_cap: int) -> str:
    return (
        f"Requests to Context.dev: {used.total} used of {total_cap} ({used.recordings} recordings that carry a paid "
        f"answer, {UNRECORDED_REQUESTS} requests of the team's log that left no recording; the count file holds "
        f"{used.stored}). {max(0, total_cap - used.total)} left."
    )


def count_before_sending(counter: Path | None, used: Used, requests: int) -> None:
    """Write the count with `requests` more, before they go out: for a fan-out whose containers hold no count file.
    Raises `EvidenceUnavailable` when it cannot be written: requests whose count cannot be kept are not sent."""
    store_count(counter, used.total + requests)


def capture_ids(capture_dir: Path) -> tuple[str, ...]:
    """The product ids of a replay capture, as recorded. Raises `ValueError` for a file that is no list of ids."""
    ids = json.loads((capture_dir / CAPTURE_IDS_FILE).read_text(encoding="utf-8"))
    if not isinstance(ids, list) or not all(isinstance(product_id, str) for product_id in ids):
        raise ValueError("The capture's id file is not a list of product ids.")
    return tuple(ids)


def stating_nothing(product_ids: Iterable[str], catalog: Catalog) -> tuple[str, ...]:
    """Of the given products, those whose data holds no allergen statement at all, in the order given."""
    products = (catalog.get_product(product_id) for product_id in dict.fromkeys(product_ids))
    return tuple(product.id for product in products if product is not None and not product.allergen_statements)


def plan(product_ids: Iterable[str], catalog: Catalog, recorded: frozenset[str], limit: int) -> Plan:
    """At most `limit` products to ask, in the order given; the rest are named with why they are not asked.
    Raises `ValueError` for a limit below 1."""
    if limit < 1:
        raise ValueError("The limit of requests must be at least 1.")
    to_ask: list[Product] = []
    already, unknown, over = [], [], []
    for product_id in dict.fromkeys(product_ids):
        product = catalog.get_product(product_id) if PRODUCT_ID.fullmatch(product_id) else None
        if product is None:
            unknown.append(product_id)
        elif product_id in recorded:
            already.append(product_id)
        elif len(to_ask) >= limit:
            over.append(product_id)
        else:
            to_ask.append(product)
    return Plan(tuple(to_ask), tuple(already), tuple(unknown), tuple(over), limit)


def payload(product: Product) -> JsonDict:
    """What one call of the fan-out receives: the product's id and the body to send. Built from the product alone."""
    return {"product_id": product.id, "request": answer_request(product)}


def dry_run_lines(planned: Plan) -> list[str]:
    """What a dry run prints: every body that would be sent, then the count and the cost. Sends nothing."""
    lines = []
    for product in planned.to_ask:
        lines.append(f"{product.id} would be sent ({CREDITS_PER_REQUEST} credits):")
        lines.append(json.dumps(answer_request(product), indent=2, ensure_ascii=False))
    lines += left_out_lines(planned)
    lines.append(
        f"Dry run: {len(planned.to_ask)} request(s) would be sent to Context.dev, {CREDITS_PER_REQUEST} credits "
        f"each, {planned.credits} credits in all (limit {planned.limit}). Nothing was sent."
    )
    return lines


def left_out_lines(planned: Plan) -> list[str]:
    """Which products of the list are not asked, and why."""
    lines = []
    if planned.already_recorded:
        lines.append(f"Already recorded, not asked again: {', '.join(planned.already_recorded)}.")
    if planned.not_in_catalog:
        lines.append(f"Not in the catalog, not asked: {', '.join(planned.not_in_catalog)}.")
    if planned.over_the_limit:
        lines.append(
            f"Over the limit of {planned.limit}, not asked in this run: {', '.join(planned.over_the_limit)}."
        )
    return lines


def ask_one(call: JsonDict, sender: BodySender) -> JsonDict:
    """One request of the fan-out: the answer as a record, or why there is none. Never raises for a refusal."""
    product_id, body = call["product_id"], call["request"]
    try:
        return sender.send(product_id, body).to_json()
    except EvidenceUnavailable as unavailable:
        refused: JsonDict = {"product_id": product_id, UNAVAILABLE_KEY: unavailable.reason}
        return refused if unavailable.raw is None else {**refused, RAW_KEY: unavailable.raw}


def keep(result: Any, product: Product, cache: EvidenceCache) -> Outcome:
    """Store one result of `ask_one` and read it. An answer is stored whatever it says: it cost credits. A refusal
    (no answer came) is kept nowhere and reads as "no evidence", with the reason. Anything that came back and
    cannot be read as an answer is stored as it is under `unreadable/`, where nothing replays it (S10)."""
    if isinstance(result, BaseException):  # `Function.map(..., return_exceptions=True)`: one call that failed
        return _nothing(product.id, wording.BATCH_CALL_FAILED.format(error=type(result).__name__))
    if isinstance(result, dict) and isinstance(result.get(UNAVAILABLE_KEY), str):
        raw = result.get(RAW_KEY)
        kept = _keep_unreadable(product.id, raw, cache.directory) if raw is not None else None
        return _nothing(product.id, result[UNAVAILABLE_KEY], kept)
    try:
        record = AnswerRecord.from_json(result)
    except ValueError:
        return _nothing(product.id, wording.UNREADABLE, _keep_unreadable(product.id, result, cache.directory))
    if record.product_id != product.id:
        return _nothing(product.id, wording.UNREADABLE, _keep_unreadable(product.id, result, cache.directory))
    cache.put(record)
    return Outcome(product.id, record, read_answer(record, product))


def _keep_unreadable(product_id: str, raw: Any, directory: Path) -> Path:
    """Write what came back, as it came, to `<directory>/unreadable/<product id>.json`. The folder is outside what
    `recorded_ids` and the cache read, so the product still counts as not recorded."""
    folder = directory / UNREADABLE_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{product_id}{SUFFIX}"
    kept = {"product_id": product_id, "received": raw}
    target.write_text(json.dumps(kept, indent=2, ensure_ascii=False, default=repr) + "\n", encoding="utf-8")
    return target


def _nothing(product_id: str, reason: str, raw_kept: Path | None = None) -> Outcome:
    return Outcome(product_id, None, Evidence(
        product_id=product_id, found=False, sentence=wording.not_found(product_id, reason),
    ), raw_kept)


def outcome_lines(outcomes: Sequence[Outcome], directory: Path) -> list[str]:
    """One line per product of a run: how its answer reads, or why there is none, and what was written."""
    lines = []
    for outcome in outcomes:
        if outcome.record is not None:
            kept = f"{directory.name}/{outcome.product_id}{SUFFIX}"
        elif outcome.raw_kept is not None:
            kept = (
                f"no recording written; what was received is kept in {directory.name}/{UNREADABLE_FOLDER}/"
                f"{outcome.raw_kept.name}, and a new run would ask and pay again"
            )
        else:
            kept = "no file written"
        lines.append(f"{outcome.product_id}: {outcome.evidence.sentence} ({kept})")
    return lines


def failure_line(outcomes: Sequence[Outcome]) -> str | None:
    """The line a run ends on when a product got no answer; `None` when every product got one."""
    failed = [outcome.product_id for outcome in outcomes if outcome.failed]
    if not failed:
        return None
    if len(failed) == len(outcomes):
        return f"FAILED: none of the {len(outcomes)} product(s) asked was answered."
    return f"FAILED for {len(failed)} of {len(outcomes)} product(s), each with its reason above: {', '.join(failed)}."


def record(
    planned: Plan, cache: EvidenceCache, ask_all: Callable[[Sequence[JsonDict]], Iterable[Any]]
) -> tuple[Outcome, ...]:
    """Ask for every planned product and keep each answer. `ask_all` receives the calls and answers one result per
    call, in order: a loop over `ask_one` here, `Function.map` on Modal."""
    calls = [payload(product) for product in planned.to_ask]
    if not calls:
        return ()
    results = iter(ask_all(calls))
    # Each answer is kept as it arrives: a run that stops half-way has stored what it already paid for.
    outcomes = [keep(result, product, cache) for product, result in zip(planned.to_ask, results, strict=False)]
    if len(outcomes) != len(calls) or next(results, _NO_MORE) is not _NO_MORE:
        raise ValueError("The batch answered another number of results than it was asked for.")
    return tuple(outcomes)


def one_by_one(sender: BodySender) -> Callable[[Sequence[JsonDict]], list[JsonDict]]:
    """`ask_all` for a local run: one request after the other through the given sender."""
    return lambda calls: [ask_one(call, sender) for call in calls]


def summarise(outcomes: Sequence[Outcome]) -> Summary:
    found = [outcome for outcome in outcomes if outcome.evidence.found]
    return Summary(
        asked=len(outcomes),
        answered=sum(1 for outcome in outcomes if outcome.record is not None),
        page_found=sum(1 for outcome in outcomes if outcome.page_found),
        matched=len(found),
        dropped=sum(1 for outcome in outcomes if outcome.page_found and not outcome.evidence.found),
        names_an_allergen=sum(1 for o in found if o.evidence.contains or o.evidence.may_contain),
    )


def table(summary: Summary) -> str:
    """The summary as the lines a run prints. Figures of this run only: a sample, never a catalog fact."""
    rows = (
        ("Products asked", summary.asked),
        ("Answers received and stored", summary.answered),
        ("A page was found", summary.page_found),
        ("The page names this product (shown as evidence)", summary.matched),
        ("Dropped: another product's page, or it could not be checked", summary.dropped),
        ("Evidence that names an allergen (contains or may contain)", summary.names_an_allergen),
        ("Credits for the answers received", summary.credits),
    )
    width = max(len(label) for label, _ in rows)
    return "\n".join(f"{label.ljust(width)}  {value}" for label, value in rows)
