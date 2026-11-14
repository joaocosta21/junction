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
the client refuses a request past it. The team approved 60 requests in all and 17 were used (docs/CONTEXTDEV.md);
going past that approval is the owner's decision, not this script's. The key is read through `tta.config` and is
never printed.
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
from tta.evidence.answers import CREDITS_PER_REQUEST, AnswersClient
from tta.evidence.cache import EvidenceCache
from tta.evidence.demo_set import demo_requests, products_with_doubt
from tta.evidence.finder import RECORDINGS_FOLDER
from tta.offers import OfferDeps, OfferService
from tta.policy import RulePolicyEngine
from tta.valio import ReplayGateway

DEFAULT_LIMIT = 10
MONDAY = 0
EXIT_OK, EXIT_USAGE, EXIT_NO_KEY = 0, 2, 3
Printer = Callable[[str], None]


def _next_monday(today: date) -> date:
    """The first Monday after today (Valio Aimo's answer B11)."""
    return today + timedelta(days=(MONDAY - today.weekday() - 1) % 7 + 1)


def demo_set(settings: Settings, catalog: ProductCatalog, out: Printer) -> tuple[str, ...]:
    """The demo's products with an allergen doubt, measured in replay. An offer that cannot be built is said and
    skipped: the list is then of the offers that could be."""
    policy = RulePolicyEngine.from_files()
    replay = ReplayGateway.from_settings(settings)
    clock = replay.clock
    offers = OfferService(OfferDeps(
        catalog=catalog, gateway=replay, policy=policy, clock=clock, day_spend=lambda _profile: Decimal(0),
    ))
    built: list[Offer] = []
    for profile_id, request in demo_requests(shipped_customers(), _next_monday(clock.now().date())):
        agent = Identity(kind=IdentityKind.AGENT, id=f"agent:{profile_id}", display_name=profile_id,
                         profile_id=profile_id)
        try:
            built.append(offers.build_offer(request, agent))
        except TtaError as error:
            out(f"No offer for {profile_id}, line “{request.lines[0].text}”: {type(error).__name__}. Skipped.")
    out(f"Demo set measured in replay at {clock.now().isoformat()} from {len(built)} offers.")
    return products_with_doubt(built)


def _arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--ids", nargs="+", metavar="ID", help="product ids to record")
    which.add_argument("--demo-set", action="store_true", help="the demo's products with an allergen doubt")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="most requests this run may send (10)")
    parser.add_argument("--dry-run", action="store_true", help="print the request bodies and the cost; send nothing")
    return parser.parse_args(argv)


def main(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    catalog: ProductCatalog | None = None,
    sender: batch.BodySender | None = None,
    directory: Path | None = None,
    out: Printer = print,
) -> int:
    """`sender`, `directory`, `settings` and `catalog` are for tests: a stand-in for Context.dev and a scratch
    folder. Without them the run uses the settings, the real client and `fixtures/evidence/`."""
    args = _arguments(argv)
    if args.limit < 1:
        out("--limit must be at least 1.")
        return EXIT_USAGE
    settings = settings or get_settings()
    catalog = catalog or ProductCatalog.from_settings(settings)
    directory = directory or settings.tta_fixtures_dir / RECORDINGS_FOLDER
    wanted = tuple(args.ids) if args.ids else demo_set(settings, catalog, out)
    out(f"Products with an allergen doubt on the list: {', '.join(wanted) or 'none'}.")
    planned = batch.plan(wanted, catalog, batch.recorded_ids(directory), args.limit)
    if args.dry_run:
        for line in batch.dry_run_lines(planned):
            out(line)
        return EXIT_OK
    for line in batch.left_out_lines(planned):
        out(line)
    if not planned.to_ask:
        out("Nothing to ask. Nothing was sent.")
        return EXIT_OK
    if sender is None and not settings.has_context_dev_key:
        out("No Context.dev key is set (CONTEXT_DEV_API_KEY), so nothing was sent.")
        return EXIT_NO_KEY
    out(f"Sending {len(planned.to_ask)} request(s) to Context.dev, {CREDITS_PER_REQUEST} credits each.")
    client = sender or AnswersClient(settings, max_calls=args.limit)  # the cap again, where the request leaves
    try:
        outcomes = batch.record(planned, EvidenceCache(directory), batch.one_by_one(client))
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    for outcome in outcomes:
        kept = f"{directory.name}/{outcome.product_id}.json" if outcome.record else "no file written"
        out(f"{outcome.product_id}: {outcome.evidence.sentence} ({kept})")
    out(batch.table(batch.summarise(outcomes)))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
