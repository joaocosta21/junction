"""The evidence batch as a fan-out on Modal (AP-7): one function mapped over products, at most 40 at a time.

Scores on the 15% exceptions (missing allergen data beyond one demo product) and is the "fan out a big batch job"
of Modal's brief. It serves no model and uses no GPU: each call is one HTTPS request to Context.dev, which reads
the manufacturer's page of one product.

    .venv/bin/python deploy/evidence_batch.py --limit 200 --dry-run     # offline: the count and the cost
    .venv/bin/modal run deploy/evidence_batch.py --limit 200            # the run

Which products: those of the replay capture whose data holds no allergen statement at all and that have no
recorded page yet (`tta.evidence.batch`), in the capture's order, at most `--limit` (default 40). The list is
computed on the machine that starts the run. Each call receives a product id and the body to send (the product's
English name, Finnish name and brand; nothing about a buyer), sends it once, and returns the answer; the starting
machine writes each answer to `fixtures/evidence/<id>.json` as it arrives and prints a summary table.

The dry run through plain Python touches no network at all. `modal run … --dry-run` prints the same and sends
nothing to Context.dev, but `modal run` itself builds this app on Modal, with the Secret.

The Context.dev key travels as its own Modal Secret, read through `tta.config` on the starting machine only, the
way `deploy/modal_app.py` does it. No call is retried: a repeated request costs as much as the first.

Names used, as the installed Modal client has them (1.6.4, checked with `inspect`; no Modal page was read):
`modal.App`, `App.function(image=, secrets=, max_containers=, timeout=, retries=)`, `App.local_entrypoint`,
`Function.map(..., order_outputs=, return_exceptions=)`, `Function.local`, `modal.Secret.from_dict`,
`modal.is_local`, `modal.Image.debian_slim`, `.uv_pip_install`, `.env`, `.add_local_dir`.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import modal

if TYPE_CHECKING:
    from tta.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "trusted-trade-agents-evidence"
APP_ROOT = "/app"
PYTHON_VERSION = "3.13"
MAX_AT_ONCE = 40  # containers, one request each: under Context.dev's 50 concurrent requests per organisation
DEFAULT_LIMIT = 40
CALL_TIMEOUT_SECONDS = 120  # the request's own deadline is 40 s and its HTTP timeout 50 s (tta.evidence.answers)
NO_RETRIES = 0
SECRET_NAME = "CONTEXT_DEV_API_KEY"  # noqa: S105 - the name of the value, not the value
# What `tta.evidence.batch` imports, at the versions of deploy/modal_app.py (tests/deploy checks they agree).
PINNED = ("pydantic==2.14.3", "pydantic-settings==2.16.3", "httpx==0.28.1")
IMAGE_ENV = {"PYTHONPATH": f"{APP_ROOT}/src", "TTA_ENV": "demo", "TTA_MODE": "replay"}
Printer = Callable[[str], None]


def secret_env(*, is_local: bool, read_settings: Callable[[], Settings] | None = None) -> dict[str, str]:
    """The Context.dev key and nothing else, read on the starting machine only. Empty when no key is set: the
    calls then answer "no Context.dev key is set" and nothing is sent."""
    if not is_local:
        return {}
    if read_settings is None:
        from tta.config import get_settings  # looked up when called, so a test can replace it

        read_settings = get_settings
    settings = read_settings()
    if not settings.has_context_dev_key or settings.context_dev_api_key is None:
        return {}
    return {SECRET_NAME: settings.context_dev_api_key.get_secret_value()}


def skipped(path: Path) -> bool:
    return any(part.startswith(".") or part == "__pycache__" for part in path.parts) or path.suffix == ".pyc"


def build_image(repo_root: Path = REPO_ROOT) -> modal.Image:
    """The package and the libraries the evidence code imports. No product file, no fixture, no key."""
    image = modal.Image.debian_slim(python_version=PYTHON_VERSION).uv_pip_install(*PINNED).env(IMAGE_ENV)
    return image.add_local_dir(repo_root / "src" / "tta", f"{APP_ROOT}/src/tta", ignore=skipped)


def build_sender() -> Any:
    """The Context.dev client of one call, inside the container: it may send exactly one request."""
    from tta.config import get_settings
    from tta.evidence.answers import AnswersClient

    return AnswersClient(get_settings(), max_calls=1)


app = modal.App(APP_NAME)
secret = modal.Secret.from_dict(secret_env(is_local=modal.is_local()))


@app.function(
    image=build_image(), secrets=[secret], max_containers=MAX_AT_ONCE, timeout=CALL_TIMEOUT_SECONDS,
    retries=NO_RETRIES,
)
def ask_page(call: dict[str, Any]) -> dict[str, Any]:
    """One product: send its prepared body to Context.dev once and return the answer, or why there is none."""
    from tta.evidence import batch

    sender = build_sender()
    try:
        return batch.ask_one(call, sender)
    finally:
        close = getattr(sender, "close", None)
        if callable(close):
            close()


def run(
    *,
    limit: int,
    dry_run: bool,
    ask_all: Callable[[Sequence[dict[str, Any]]], Iterable[Any]],
    out: Printer = print,
    settings: Settings | None = None,
    catalog: Any = None,
    directory: Path | None = None,
) -> int:
    """Plan, then print (dry run) or ask and keep. `ask_all` is `ask_page.map` on Modal, and a stand-in in a
    test. Returns the number of requests that were handed to `ask_all`."""
    from tta.catalog import ProductCatalog
    from tta.config import get_settings
    from tta.evidence import batch
    from tta.evidence.cache import EvidenceCache
    from tta.evidence.finder import RECORDINGS_FOLDER

    settings = settings or get_settings()
    catalog = catalog or ProductCatalog.from_settings(settings)
    directory = directory or settings.tta_fixtures_dir / RECORDINGS_FOLDER
    silent = batch.stating_nothing(batch.capture_ids(settings.replay_capture_dir), catalog)
    planned = batch.plan(silent, catalog, batch.recorded_ids(directory), limit)
    out(
        f"{len(silent)} products of the capture {settings.replay_capture_dir.name} hold no allergen statement; "
        f"{len(planned.already_recorded)} of them already have a recorded page."
    )
    if dry_run:
        out(
            f"Dry run: {len(planned.to_ask)} request(s) would be sent to Context.dev, at most {MAX_AT_ONCE} at a "
            f"time, {batch.CREDITS_PER_REQUEST} credits each, {planned.credits} credits in all (limit {limit}). "
            "Nothing was sent."
        )
        return 0
    if not planned.to_ask:
        out("Nothing to ask. Nothing was sent.")
        return 0
    out(f"Asking for {len(planned.to_ask)} product(s), at most {MAX_AT_ONCE} at a time, {planned.credits} credits.")
    outcomes = batch.record(planned, EvidenceCache(directory), ask_all)
    out(batch.table(batch.summarise(outcomes)))
    out(f"Answers were written to {directory}. Figures of this run only: a sample, not a catalog fact.")
    return len(outcomes)


def on_modal(calls: Sequence[dict[str, Any]]) -> Iterable[Any]:
    """The fan-out: one container per call, results in the order of the calls, a failed call as its exception."""
    return ask_page.map(calls, order_outputs=True, return_exceptions=True)


@app.local_entrypoint()
def main(limit: int = DEFAULT_LIMIT, dry_run: bool = False) -> None:
    run(limit=limit, dry_run=dry_run, ask_all=on_modal)


def _refuse_to_send(calls: Sequence[dict[str, Any]]) -> Iterable[Any]:
    raise SystemExit("Run without --dry-run goes through Modal: .venv/bin/modal run deploy/evidence_batch.py")


if __name__ == "__main__":  # plain Python: the offline dry run only
    parser = argparse.ArgumentParser(description="The evidence batch: the offline dry run.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--dry-run", action="store_true", required=True)
    arguments = parser.parse_args()
    run(limit=arguments.limit, dry_run=True, ask_all=_refuse_to_send)
    sys.exit(0)
