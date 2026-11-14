"""Record the manufacturer's page of products that carry an allergen doubt and have no recorded page yet (AP-3).

Usage (from the repository root):
    .venv/bin/python scripts/record_evidence.py --demo-set --dry-run
    .venv/bin/python scripts/record_evidence.py --demo-set
    .venv/bin/python scripts/record_evidence.py --ids 465793 464517 --limit 2

`--demo-set` measures the list in replay (no call to Valio Aimo): the products rule P-04 sends to a person in the
demo's offers (`tta.evidence.demo_set`). `--dry-run` prints each request body and the cost and sends nothing; it
needs no key. A real run sends, for each product, its English name, its Finnish name and its brand to
`api.context.dev` through the gateway's own finder, and writes `fixtures/evidence/<id>.json` in the format the
gateway replays. A product that already has a file there is never asked again.

`--limit` (default 10) is a hard cap on the requests of one run: products beyond it are named and not asked, and
the client refuses a request past it. `--total-cap` (default 60, the total the team approved, docs/CONTEXTDEV.md)
is a cap across runs: the requests counted so far are the larger of the count file
(`<TTA_DATA_DIR>/evidence/request-count.json`, the gateway's own) and a floor that a fresh checkout cannot lose
(`tta.evidence.batch.requests_used`); every run, also a dry run, prints "N used of 60". The key is read through
`tta.config` and is never printed.

Exit status: 0 every product asked was answered (or nothing was to ask); 2 a wrong argument; 3 no key; 4 nothing
was answered; 5 some products were not answered; 6 an offer of the demo set could not be built, so the list may be
short; 7 the total is spent; 8 the count of requests could not be read or written.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from tta.catalog import ProductCatalog
from tta.config import Settings, get_settings
from tta.contracts.common import Identity, IdentityKind
from tta.contracts.errors import TtaError
from tta.contracts.offer import Offer
from tta.customers.loader import shipped_customers
from tta.evidence import batch
from tta.evidence.answers import CREDITS_PER_REQUEST, AnswersClient, EvidenceUnavailable
from tta.evidence.cache import EvidenceCache
from tta.evidence.demo_set import demo_requests, products_with_doubt
from tta.evidence.finder import CACHE_FOLDER, COUNT_FILE, RECORDINGS_FOLDER
from tta.offers import OfferDeps, OfferService
from tta.policy import RulePolicyEngine
from tta.valio import ReplayGateway

DEFAULT_LIMIT = 10
MONDAY = 0
EXIT_OK, EXIT_USAGE, EXIT_NO_KEY = 0, 2, 3
EXIT_NOTHING_ANSWERED, EXIT_SOME_FAILED, EXIT_OFFER_SKIPPED, EXIT_TOTAL_SPENT, EXIT_COUNT_UNREADABLE = 4, 5, 6, 7, 8
Printer = Callable[[str], None]


def _next_monday(today: date) -> date:
    """The first Monday after today (Valio Aimo's answer B11)."""
    return today + timedelta(days=(MONDAY - today.weekday() - 1) % 7 + 1)


def demo_set(settings: Settings, catalog: ProductCatalog, out: Printer) -> tuple[tuple[str, ...], int]:
    """(the demo's products with an allergen doubt, measured in replay; the offers that could not be built). An
    offer that cannot be built is named with its reason and counted: the list is then of the offers that could be,
    and the run's exit status says so."""
    policy = RulePolicyEngine.from_files()
    replay = ReplayGateway.from_settings(settings)
    clock = replay.clock
    offers = OfferService(OfferDeps(
        catalog=catalog, gateway=replay, policy=policy, clock=clock, day_spend=lambda _profile: Decimal(0),
    ))
    built: list[Offer] = []
    skipped = 0
    for profile_id, request in demo_requests(shipped_customers(), _next_monday(clock.now().date())):
        agent = Identity(kind=IdentityKind.AGENT, id=f"agent:{profile_id}", display_name=profile_id,
                         profile_id=profile_id)
        try:
            built.append(offers.build_offer(request, agent))
        except TtaError as error:
            skipped += 1
            out(f"No offer for {profile_id}, line “{request.lines[0].text}”: {type(error).__name__}: {error}. Skipped.")
    out(f"Demo set measured in replay at {clock.now().isoformat()} from {len(built)} offers.")
    if skipped:
        out(f"{skipped} offer(s) could not be built: the list below may miss the products they would have added.")
    return products_with_doubt(built), skipped


def _arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--ids", nargs="+", metavar="ID", help="product ids to record")
    which.add_argument("--demo-set", action="store_true", help="the demo's products with an allergen doubt")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="most requests this run may send (10)")
    parser.add_argument("--total-cap", type=int, default=batch.DEFAULT_TOTAL_CAP,
                        help="most requests in all, across runs (60, the total the team approved)")
    parser.add_argument("--dry-run", action="store_true", help="print the request bodies and the cost; send nothing")
    return parser.parse_args(argv)


def _status(outcomes: Sequence[batch.Outcome], skipped_offers: int) -> int:
    failed = sum(1 for outcome in outcomes if outcome.failed)
    if outcomes and failed == len(outcomes):
        return EXIT_NOTHING_ANSWERED
    if failed:
        return EXIT_SOME_FAILED
    return EXIT_OFFER_SKIPPED if skipped_offers else EXIT_OK


def main(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    catalog: ProductCatalog | None = None,
    sender: batch.BodySender | None = None,
    directory: Path | None = None,
    counter: Path | None = None,
    out: Printer = print,
) -> int:
    """`sender`, `directory`, `counter`, `settings` and `catalog` are for tests: a stand-in for Context.dev and
    scratch files. Without them the run uses the settings, the real client, `fixtures/evidence/` and the count
    file beside the gateway's stored answers."""
    args = _arguments(argv)
    if args.limit < 1 or args.total_cap < 1:
        out("--limit and --total-cap must be at least 1.")
        return EXIT_USAGE
    settings = settings or get_settings()
    catalog = catalog or ProductCatalog.from_settings(settings)
    directory = directory or settings.tta_fixtures_dir / RECORDINGS_FOLDER
    counter = counter or settings.tta_data_dir / CACHE_FOLDER / COUNT_FILE
    try:
        used = batch.requests_used(directory, counter)
    except EvidenceUnavailable as unavailable:
        out(f"Nothing was sent: {unavailable.reason} ({counter}).")
        return EXIT_COUNT_UNREADABLE
    wanted, skipped_offers = (tuple(args.ids), 0) if args.ids else demo_set(settings, catalog, out)
    out(f"Products with an allergen doubt on the list: {', '.join(wanted) or 'none'}.")
    left = args.total_cap - used.total
    if left < 1:
        out(batch.used_line(used, args.total_cap))
        out("The total is spent: nothing can be sent. Going past it is the team's decision (--total-cap).")
        return EXIT_TOTAL_SPENT
    planned = batch.plan(wanted, catalog, batch.recorded_ids(directory), min(args.limit, left))
    if args.dry_run:
        *bodies, last = batch.dry_run_lines(planned)
        for line in (*bodies, batch.used_line(used, args.total_cap), last):
            out(line)
        return _status((), skipped_offers)
    for line in (*batch.left_out_lines(planned), batch.used_line(used, args.total_cap)):
        out(line)
    if not planned.to_ask:
        out("Nothing to ask. Nothing was sent.")
        return _status((), skipped_offers)
    if sender is None and not settings.has_context_dev_key:
        out("No Context.dev key is set (CONTEXT_DEV_API_KEY), so nothing was sent.")
        return EXIT_NO_KEY
    out(f"Sending {len(planned.to_ask)} request(s) to Context.dev, {CREDITS_PER_REQUEST} credits each.")
    # Both caps again, where the request leaves: this run's requests on top of the count, never past the total.
    client = sender or AnswersClient(
        settings, max_calls=used.total + len(planned.to_ask), counter=counter, floor=used.floor,
    )
    try:
        outcomes = batch.record(planned, EvidenceCache(directory), batch.one_by_one(client))
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    for line in batch.outcome_lines(outcomes, directory):
        out(line)
    out(batch.table(batch.summarise(outcomes)))
    failure = batch.failure_line(outcomes)
    if failure:
        out(failure)
    return _status(outcomes, skipped_offers)


if __name__ == "__main__":
    sys.exit(main())
