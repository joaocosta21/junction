"""The public demonstration of the gateway on Modal (task T14, docs/DEPLOY.md).

Scores on the 30% "working end-to-end demo" (a link a judge can open) and the 15% "credible path toward
production" (one command, the secrets kept out of the code and the image, the data on a Volume).

    .venv/bin/modal deploy --strategy recreate deploy/modal_app.py

One container at most: the database is SQLite and the rate limiter and the pages' run log live in one process.
It takes many requests at once. `TTA_ENV=demo`, `TTA_MODE=replay`, `TTA_DEMO_CLOCK=2026-11-12T14:15:00+02:00`: the
public link answers from the recorded capture and judges order deadlines against the demo clock (Thursday
12 Nov 2026 14:15, Helsinki; Valio Aimo said on 14 Nov that its test data is static and the date is ours to
choose). The clock setting is honoured in replay only and refused outside dev and demo (AIMO/build/handback/B0.md).

Data: the call budget and the recordings of live answers are written straight to a Volume mounted at the data
directory. SQLite works on the container's own disk and a whole copy of the database is kept on the Volume: it is
put back at start and copied again soon after each change, then the Volume is committed. Modal's documentation
gives no guidance for SQLite on a Volume and says Volumes do not support distributed file locking; SQLite says WAL
mode, which the store uses, does not work over a network file system; Modal's own SQLite example builds the
database off the Volume and copies it in. So the live database never sits on the Volume.

Names used, as documented by the Modal client this was written with (1.6.4): `modal.App`, `modal.Image.debian_slim`,
`.uv_pip_install`, `.env`, `.add_local_dir`, `.add_local_file`, `modal.Volume.from_name`, `.commit`,
`modal.Secret.from_dict`, `modal.is_local`, `@app.function(max_containers=..., min_containers=...,
scaledown_window=..., cpu=..., memory=...)`, `@modal.concurrent(max_inputs=...)`, `@modal.asgi_app(label=...)`.

The witness (AP-10): when `SUPPLIER_DATABASE_URL` is set on the deploying machine, a second function runs every
hour, reads the head of the audit trail from the supplier's view with the supplier's read-only login, and checks
that the head it noted at its last run is still at its place (`deploy/witness.py`); its notes are kept in a
`modal.Dict`. Without that value no such function exists and nothing is scheduled. Names used for it, checked
with `inspect` on the installed client (1.6.4; no Modal page was read): `@app.function(schedule=...)`,
`modal.Period(hours=...)`, `modal.Dict.from_name(..., create_if_missing=True)`, `Dict.get`, `Dict.put`.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import sqlite3
import sys
import threading
import time
from collections.abc import Callable, Iterator, Mapping, MutableMapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import modal

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

    from tta.config import Settings

logger = logging.getLogger(__name__)

# On the deploying machine the repository; inside the container this file is /root/modal_app.py and the paths below
# that start from it are not used.
REPO_ROOT = Path(__file__).resolve().parents[1]

APP_NAME = "trusted-trade-agents"
WEB_LABEL = APP_NAME  # https://<workspace>--trusted-trade-agents.modal.run (docs/DEPLOY.md)
VOLUME_NAME = "trusted-trade-agents-data"
PYTHON_VERSION = "3.13"  # pyproject.toml: requires-python >= 3.13

# The repository's layout under /app, so that `tta.config.REPO_ROOT` (two folders above `tta/config.py`) is /app
# there as it is the repository root here: the pages read docs/ASSUMPTIONS.md from it.
APP_ROOT = "/app"
VOLUME_MOUNT = "/data"  # TTA_DATA_DIR: the call budget, the recordings and the kept copy of the database
LOCAL_DB = "/tmp/tta/tta.sqlite3"  # noqa: S108 - the container's own disk, where SQLite works
VOLUME_DB = f"{VOLUME_MOUNT}/tta.sqlite3"

MAX_CONTAINERS = 1  # SQLite, the rate limiter and the run log are per process
MIN_CONTAINERS = 0  # scale to zero when idle
SCALEDOWN_SECONDS = 600  # idle time before the container stops; Modal accepts 2 to 3600
MAX_CONCURRENT_REQUESTS = 100  # the value of Modal's own ASGI examples; requests above it wait
CPU_CORES = 1.0  # Modal's default request is 0.125 cores; loading the catalog takes about 2 s on one core
MEMORY_MIB = 1024  # measured locally: about 630 MiB at its peak with the catalog loaded
SAVE_DELAY_SECONDS = 1.0  # one copy for the writes of one burst of requests

PRODUCT_FILE = "valio_aimo_junction26_product_data.json"
RELIABILITY_FILE = "valio_aimo_junction26_delivery_reliability.csv"
CARBON_FILE = "valio_aimo_junction26_carbon_footprint.csv"
ASSUMPTIONS_FILE = "docs/ASSUMPTIONS.md"

# The libraries pyproject.toml declares, at the versions the test suite ran with (tests/deploy checks both), plus
# Starlette, whose `Mount.matches` the application overrides. Modal runs the ASGI app itself and brings its own
# client, so neither uvicorn nor modal is installed.
PINNED = (
    "fastapi==0.162.7",
    "starlette==1.10.0",
    "pydantic==2.14.3",
    "pydantic-settings==2.16.3",
    "httpx==0.28.1",
    "pyyaml==6.0.3",
    "jinja2==3.1.6",
    "python-multipart==0.0.33",
    "google-genai==3.3.0",
    "mcp==2.3.0",
    "psycopg[binary]==3.3.9",
    "cryptography==50.0.2",  # declared in pyproject.toml on 14 Nov for src/tta/api/signing.py
)
NOT_INSTALLED = ("modal", "uvicorn")

DEPLOYED_CALL_BUDGET = 120
# The public link's settings (AP-2): the recorded capture, at the clock the demo is told at.
DEPLOYED_MODE = "replay"
DEMO_CLOCK = "2026-11-12T14:15:00+02:00"
# Settings that are no secret and are the deploying machine's to choose: they travel with the Secret because that is
# the one channel from that machine's environment to the container. `TTA_DB_SCHEMA` names a new PostgreSQL schema
# when the deployed audit trail can no longer be read by this build (the old trail stays, untouched).
SCHEMA_NAME_IN_CONTAINER = "TTA_DB_SCHEMA"
# The key offers and orders are signed with (S8). Without it the container generates a demo key at every cold
# start, so a signature made before a restart no longer verifies against `/.well-known/jwks.json`.
SIGNING_KEY_NAME = "TTA_SIGNING_KEY"  # noqa: S105 - the name of the value, not the value
# Valio Aimo's own suggestion on an offer, on or off: sent only when the deploying machine set it.
SUGGESTIONS_NAME = "TTA_SUPPLIER_SUGGESTIONS"
SUGGESTIONS_FIELD = "tta_supplier_suggestions"
# The model key stays on the deploying machine unless its shell says otherwise: the owner dropped the model on
# 14 Nov, and the public link reads requests with the recordings and the fixed rules.
MODEL_KEY_NAME = "GEMINI_API_KEY"
MODEL_OPT_IN = "TTA_DEPLOY_WITH_MODEL"
MODEL_OPT_IN_VALUE = "1"
# The Context.dev key stays on the deploying machine too (security review M4): with it, any visitor of the public
# link could make the gateway send 100-credit lookups until its count is spent. The link shows the recorded pages
# (fixtures/evidence/) and says of any other product that no lookup is made.
EVIDENCE_KEY_NAME = "CONTEXT_DEV_API_KEY"  # noqa: S105 - the name of the value, not the value
EVIDENCE_OPT_IN = "TTA_DEPLOY_WITH_EVIDENCE_LOOKUPS"
# The witness of the audit head (AP-10). The supplier's read-only login is read from `tta.config` when it carries
# the field, else from the deploying shell's environment; `.env` is never opened here.
SUPPLIER_URL_NAME = "SUPPLIER_DATABASE_URL"
SUPPLIER_URL_FIELD = "supplier_database_url"
WITNESS_NOTES = "trusted-trade-agents-witness"  # a modal.Dict: one note per schema
WITNESS_EVERY_HOURS = 1
WITNESS_CPU_CORES = 0.25
WITNESS_FILE = "witness.py"
WITNESS_REMOTE = f"/root/{WITNESS_FILE}"  # beside this file in the container, so `import witness` finds it
WITNESS_CONNECT_TIMEOUT_SECONDS = 5

IMAGE_ENV = {
    "PYTHONPATH": f"{APP_ROOT}/src",
    "TTA_ENV": "demo",
    "TTA_MODE": DEPLOYED_MODE,
    "TTA_DEMO_CLOCK": DEMO_CLOCK,
    "TTA_DATA_DIR": VOLUME_MOUNT,
    "TTA_DB_PATH": LOCAL_DB,
    "TTA_FIXTURES_DIR": f"{APP_ROOT}/fixtures",
    "TTA_PRODUCT_FILE": f"{APP_ROOT}/{PRODUCT_FILE}",
    "TTA_RELIABILITY_FILE": f"{APP_ROOT}/{RELIABILITY_FILE}",
    "TTA_CARBON_FILE": f"{APP_ROOT}/{CARBON_FILE}",
    # The human approved 150 calls to the Valio mock for the overnight run; 10 were used before the deployment.
    # In replay no call is made; if the mode is ever set to live again, the app may make at most this many.
    "TTA_VALIO_CALL_BUDGET": str(DEPLOYED_CALL_BUDGET),
}

# The values the public link may receive from the deploying machine's settings: the Valio key and base URL, the
# Aiven database URL, the signing key, and the two settings that are no secret.
SECRET_NAMES = (
    "VALIO_AIMO_API_KEY", "VALIO_AIMO_BASE_URL", "DATABASE_URL", SIGNING_KEY_NAME, SUGGESTIONS_NAME,
    SCHEMA_NAME_IN_CONTAINER,
)  # and `MODEL_KEY_NAME` and `EVIDENCE_KEY_NAME`, each only with its opt-in


# --- the secret ---------------------------------------------------------------------------------------------------


def supplier_url(settings: Settings, environ: Mapping[str, str]) -> str | None:
    """The supplier's read-only database URL, when one is set: the setting first, then the shell's environment."""
    # The one guarded read left (S18): `supplier_database_url` is not a field of `tta.config` on 14 Nov.
    chosen = getattr(settings, SUPPLIER_URL_FIELD, None)
    value = chosen.get_secret_value() if hasattr(chosen, "get_secret_value") else chosen
    if not isinstance(value, str) or not value.strip():
        value = environ.get(SUPPLIER_URL_NAME, "")
    return value.strip() or None


def witness_secret_values(settings: Settings, environ: Mapping[str, str]) -> dict[str, str]:
    """What the witness alone receives: the supplier's read-only URL and the schema to read, when one was chosen.
    Empty without the URL. The gateway's own Secret never holds the supplier's login, nor the witness the gateway's."""
    url = supplier_url(settings, environ)
    if url is None:
        return {}
    schema = settings.tta_db_schema.strip()
    return {SUPPLIER_URL_NAME: url, **({SCHEMA_NAME_IN_CONTAINER: schema} if schema else {})}


def witness_env(*, is_local: bool, read_settings: Callable[[], Settings] | None = None) -> dict[str, str]:
    """As `secret_env`, for the witness: read on the deploying machine only."""
    if not is_local:
        return {}
    if read_settings is None:
        from tta.config import get_settings  # looked up when called, so a test can replace it

        read_settings = get_settings
    return witness_secret_values(read_settings(), os.environ)


def with_model(environ: Mapping[str, str]) -> bool:
    """True when the deploying shell asked for the model key to travel (`TTA_DEPLOY_WITH_MODEL=1`)."""
    return environ.get(MODEL_OPT_IN, "").strip() == MODEL_OPT_IN_VALUE


def with_evidence_lookups(environ: Mapping[str, str]) -> bool:
    """True when the deploying shell asked for the Context.dev key to travel
    (`TTA_DEPLOY_WITH_EVIDENCE_LOOKUPS=1`)."""
    return environ.get(EVIDENCE_OPT_IN, "").strip() == MODEL_OPT_IN_VALUE


def secret_values(settings: Settings, *, model: bool = False, evidence_lookups: bool = False) -> dict[str, str]:
    """The values the app reads from its environment, as the deploying machine has them. A value that is not
    set is left out: without the supplier key the app answers from the recorded capture, without the address it
    uses its default, and without the signing key it signs with a demo key of its own. The model key and the
    Context.dev key are left out even when they are set, unless `model` or `evidence_lookups` is true."""
    values: dict[str, str] = {}
    if settings.has_valio_key and settings.valio_aimo_api_key is not None:
        values["VALIO_AIMO_API_KEY"] = settings.valio_aimo_api_key.get_secret_value()
    if "valio_aimo_base_url" in settings.model_fields_set:
        values["VALIO_AIMO_BASE_URL"] = settings.valio_aimo_base_url
    if model and settings.has_gemini_key and settings.gemini_api_key is not None:
        values[MODEL_KEY_NAME] = settings.gemini_api_key.get_secret_value()
    if settings.has_database_url and settings.database_url is not None:
        values["DATABASE_URL"] = settings.database_url.get_secret_value()
    if evidence_lookups and settings.has_context_dev_key and settings.context_dev_api_key is not None:
        values[EVIDENCE_KEY_NAME] = settings.context_dev_api_key.get_secret_value()
    if settings.has_signing_key and settings.tta_signing_key is not None:
        values[SIGNING_KEY_NAME] = settings.tta_signing_key.get_secret_value()
    if SUGGESTIONS_FIELD in settings.model_fields_set:
        values[SUGGESTIONS_NAME] = "true" if settings.tta_supplier_suggestions else "false"
    if settings.tta_db_schema.strip():
        values[SCHEMA_NAME_IN_CONTAINER] = settings.tta_db_schema.strip()
    return values


def _evidence_note(values: Mapping[str, str], evidence_lookups: bool) -> str:
    if EVIDENCE_KEY_NAME in values:
        return (
            f"The Context.dev key is sent ({EVIDENCE_OPT_IN}={MODEL_OPT_IN_VALUE}): the public link may send lookups, "
            "100 credits each, up to the gateway's own count."
        )
    if evidence_lookups:
        return (
            f"{EVIDENCE_OPT_IN}={MODEL_OPT_IN_VALUE} is set but no {EVIDENCE_KEY_NAME} is: no Context.dev key is "
            "sent."
        )
    return (
        "The Context.dev key is not sent: the public link shows recorded pages only, makes no lookup and spends "
        "no credit."
    )


def deploy_notes(
    values: Mapping[str, str], witness_values: Mapping[str, str], *, model: bool, evidence_lookups: bool = False
) -> tuple[str, ...]:
    """What a deployment says about its optional settings, by name only: never a value."""
    if MODEL_KEY_NAME in values:
        model_line = f"The model key is sent ({MODEL_OPT_IN}={MODEL_OPT_IN_VALUE}): the public link may call the model."
    elif model:
        model_line = f"{MODEL_OPT_IN}={MODEL_OPT_IN_VALUE} is set but no {MODEL_KEY_NAME} is: no model key is sent."
    else:
        model_line = "The model key is not sent: requests are read by the recordings and the fixed rules."
    not_set = {
        SIGNING_KEY_NAME: "the public link signs with a demo key that changes at every cold start",
        SUGGESTIONS_NAME: "the gateway's own default applies",
        SCHEMA_NAME_IN_CONTAINER: "the audit trail is in the environment's schema",
    }
    lines = [model_line, _evidence_note(values, evidence_lookups)]
    lines += [f"{name} is not set: {effect}." for name, effect in not_set.items() if name not in values]
    lines += [f"{name} is sent in the Secret." for name in not_set if name in values]
    if SUPPLIER_URL_NAME not in witness_values:
        lines.append(f"{SUPPLIER_URL_NAME} is not set: no witness of the audit head is scheduled.")
    return tuple(lines)


def secret_env(*, is_local: bool, read_settings: Callable[[], Settings] | None = None) -> dict[str, str]:
    """What the Secret holds. Read through `tta.config` (the environment, then `.env`) on the deploying machine only;
    inside the container the values are already in the environment and nothing is read (as Modal's own
    `Secret.from_local_environ` does)."""
    if not is_local:
        return {}
    if read_settings is None:
        from tta.config import get_settings  # looked up when called, so a test can replace it

        read_settings = get_settings
    return secret_values(
        read_settings(), model=with_model(os.environ), evidence_lookups=with_evidence_lookups(os.environ),
    )


# --- the image ----------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Source:
    """One file or folder of the repository and where it goes in the container."""

    local: Path
    remote: str
    is_dir: bool


def skipped(path: Path) -> bool:
    """Left out of a folder: caches, compiled files and anything hidden (`.env`, `.DS_Store`). Modal asks this of
    each path relative to the folder it adds."""
    return any(part.startswith(".") or part == "__pycache__" for part in path.parts) or path.suffix == ".pyc"


def image_sources(repo_root: Path = REPO_ROOT) -> tuple[Source, ...]:
    """The package with its YAML, templates and static files, the product file and the two CSV files, the agent,
    Valio and evidence fixtures, the witness's module, and the assumptions page when it exists. Nothing else of the
    repository."""
    sources = [
        Source(repo_root / "src" / "tta", f"{APP_ROOT}/src/tta", is_dir=True),
        *(Source(repo_root / name, f"{APP_ROOT}/{name}", is_dir=False)
          for name in (PRODUCT_FILE, RELIABILITY_FILE, CARBON_FILE)),
        *(Source(repo_root / "fixtures" / name, f"{APP_ROOT}/fixtures/{name}", is_dir=True)
          for name in ("valio", "agent", "evidence")),
    ]
    sources.append(Source(repo_root / "deploy" / WITNESS_FILE, WITNESS_REMOTE, is_dir=False))
    if (repo_root / ASSUMPTIONS_FILE).is_file():
        sources.append(Source(repo_root / ASSUMPTIONS_FILE, f"{APP_ROOT}/{ASSUMPTIONS_FILE}", is_dir=False))
    return tuple(sources)


def build_image(repo_root: Path = REPO_ROOT) -> modal.Image:
    """Libraries and environment first: the local files are added at container start, after every build step."""
    image = modal.Image.debian_slim(python_version=PYTHON_VERSION).uv_pip_install(*PINNED).env(IMAGE_ENV)
    for source in image_sources(repo_root):
        if source.is_dir:
            image = image.add_local_dir(source.local, source.remote, ignore=skipped)
        else:
            image = image.add_local_file(source.local, source.remote)
    return image


# --- the database copy on the Volume -------------------------------------------------------------------------------


def restore(working: Path, kept: Path) -> bool:
    """Put the kept copy on local disk before the gateway opens its database. False when there is none yet."""
    working.parent.mkdir(parents=True, exist_ok=True)
    if not kept.is_file():
        return False
    shutil.copyfile(kept, working)
    return True


def snapshot(working: Path, kept: Path) -> None:
    """A consistent copy of the database, also of the rows still in its WAL file, taken with SQLite's backup API on
    local disk and then put on the Volume in one step: a reader of the kept copy sees the old one or the new one."""
    local_copy = working.with_name(f"{working.name}.copy")
    partial = kept.with_name(f"{kept.name}.partial")
    source = sqlite3.connect(working)
    target = sqlite3.connect(local_copy)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    shutil.copyfile(local_copy, partial)
    os.replace(partial, kept)


class DatabaseSaver:
    """Copies the database to the Volume and commits the Volume, soon after it changed.

    `wake()` is called after each request; one thread waits for it, lets the burst settle for `delay_seconds`, and
    copies only when SQLite's `data_version` says another connection changed the database since the last copy. A
    failed copy or commit is logged and made again at the next wake; Modal's own background commits and its
    commit at shutdown also run.
    """

    def __init__(
        self, working: Path, kept: Path, commit: Callable[[], None], *, delay_seconds: float = SAVE_DELAY_SECONDS
    ) -> None:
        self._working = working
        self._kept = kept
        self._commit = commit
        self._delay_seconds = delay_seconds
        self._wanted = threading.Event()
        self._saving = threading.Lock()
        self._watching = threading.Lock()
        self._watch: sqlite3.Connection | None = None  # read only for `data_version`, under `_watching`
        self._saved_version: int | None = None  # `data_version` of `_watch` at the last copy

    def wake(self) -> None:
        self._wanted.set()

    def start(self) -> threading.Thread:
        thread = threading.Thread(target=self._run, name="tta-database-saver", daemon=True)
        thread.start()
        return thread

    def close(self) -> None:
        """Stop watching the database. A later check opens a new watch and copies once more."""
        with self._watching:
            if self._watch is not None:
                self._watch.close()
            self._watch, self._saved_version = None, None

    def save_if_changed(self) -> bool:
        version = self._version()
        if version is None or version == self._saved_version:
            return False
        if not self.save():
            return False
        self._saved_version = version
        return True

    def save(self) -> bool:
        """Copy and commit now. Also called once at shutdown, after the gateway closed its database."""
        with self._saving:
            if not self._working.is_file():
                return False
            try:
                snapshot(self._working, self._kept)
                self._commit()
            except Exception:  # a background thread has no caller to raise to: logged, and made again later
                logger.exception("The database could not be saved to the Volume; it is tried again at the next change.")
                return False
        return True

    def _version(self) -> int | None:
        """SQLite's `data_version` of the watch: it changes when another connection commits. None when there is no
        database yet, or it cannot be read (logged; the next check opens a new watch)."""
        if not self._working.is_file():
            return None
        with self._watching:
            try:
                if self._watch is None:
                    self._watch = sqlite3.connect(self._working, check_same_thread=False)
                return int(self._watch.execute("PRAGMA data_version").fetchone()[0])
            except sqlite3.Error:
                logger.exception("The database could not be watched for changes; it is tried again at the next one.")
        self.close()
        return None

    def _run(self) -> None:
        while True:
            self._wanted.wait()
            time.sleep(self._delay_seconds)
            self._wanted.clear()
            self.save_if_changed()


class SaveAfterRequests:
    """The gateway's ASGI application, waking the saver after each request and saving once more at shutdown."""

    def __init__(self, app: ASGIApp, saver: DatabaseSaver) -> None:
        self._app = app
        self._saver = saver

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self._app(scope, receive, self._saving_before_shutdown(send))
            return
        try:
            await self._app(scope, receive, send)
        finally:
            if scope["type"] == "http":
                self._saver.wake()

    def _saving_before_shutdown(self, send: Send) -> Send:
        async def sending(message: Message) -> None:
            if message["type"] == "lifespan.shutdown.complete":
                await asyncio.to_thread(self._saver.save)
            await send(message)

        return sending


# --- the Modal app -------------------------------------------------------------------------------------------------

app = modal.App(APP_NAME)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
SECRET_ENV = secret_env(is_local=modal.is_local())
secret = modal.Secret.from_dict(SECRET_ENV)


@app.function(
    image=build_image(),
    secrets=[secret],
    volumes={VOLUME_MOUNT: volume},
    max_containers=MAX_CONTAINERS,
    min_containers=MIN_CONTAINERS,
    scaledown_window=SCALEDOWN_SECONDS,
    cpu=CPU_CORES,
    memory=MEMORY_MIB,
)
@modal.concurrent(max_inputs=MAX_CONCURRENT_REQUESTS)
@modal.asgi_app(label=WEB_LABEL)
def web() -> SaveAfterRequests:
    """Runs once when the container starts: the database back on local disk, the gateway, then the saver."""
    from tta.api import create_app  # from the image (PYTHONPATH), only inside the container

    working, kept = Path(LOCAL_DB), Path(VOLUME_DB)
    logger.info("Database copy on the Volume: %s.", "restored" if restore(working, kept) else "none yet")
    gateway = create_app()
    saver = DatabaseSaver(working, kept, volume.commit)
    saver.start()
    return SaveAfterRequests(gateway, saver)


# --- the witness of the audit head (AP-10) -------------------------------------------------------------------------


def witness_is_wanted(*, is_local: bool, secret_env: Mapping[str, str], environ: Mapping[str, str]) -> bool:
    """True when the supplier's login is there to read with: in the Secret on the deploying machine, in the
    environment inside the container. Without it the witness is not defined and nothing is scheduled."""
    return bool((secret_env if is_local else environ).get(SUPPLIER_URL_NAME, "").strip())


class DictNotes(MutableMapping[str, Any]):
    """A `modal.Dict` as the mapping the witness writes its notes to."""

    def __init__(self, store: Any) -> None:
        self._store = store

    def __getitem__(self, key: str) -> Any:
        value = self._store.get(key)
        if value is None:
            raise KeyError(key)
        return value

    def __setitem__(self, key: str, value: Any) -> None:
        self._store.put(key, value)

    def __delitem__(self, key: str) -> None:
        raise TypeError("A note of the witness is never removed.")

    def __iter__(self) -> Iterator[str]:
        return iter(self._store.keys())

    def __len__(self) -> int:
        return int(self._store.len())


def run_witness(connect: Callable[[], Any], notes: MutableMapping[str, Any], environ: Mapping[str, str]) -> str:
    """One run of the witness. Returns its sentence; raises `RuntimeError` with the sentence when the trail was
    shortened or rewritten, so the run shows as failed in Modal's dashboard. The URL is never logged or raised."""
    import witness  # deploy/witness.py: beside this file in the container

    schema = environ.get(SCHEMA_NAME_IN_CONTAINER, "").strip() or witness.DEFAULT_SCHEMA
    connection = connect()
    try:
        verdict = witness.witness_once(connection, notes, schema, datetime.now(UTC))
    finally:
        connection.close()
    if not verdict.ok:
        logger.error("Audit witness, schema %s: %s", schema, verdict.sentence)
        raise RuntimeError(verdict.sentence)
    if verdict.warning:  # the trail is intact and has not moved for long: said, and the run does not fail
        logger.warning("Audit witness, schema %s: %s", schema, verdict.sentence)
        return verdict.sentence
    logger.info("Audit witness, schema %s: %s", schema, verdict.sentence)
    return verdict.sentence


def _supplier_connection() -> Any:
    """The supplier's read-only login, inside the container. A failure is reported by its class only: libpq's own
    message can repeat the URL."""
    import psycopg

    try:
        return psycopg.connect(
            os.environ[SUPPLIER_URL_NAME], autocommit=True, connect_timeout=WITNESS_CONNECT_TIMEOUT_SECONDS,
            application_name="tta-audit-witness",
        )
    except psycopg.Error as error:
        raise RuntimeError(f"The supplier's login could not connect ({type(error).__name__}).") from None


WITNESS_ENV = witness_env(is_local=modal.is_local())
if modal.is_local():  # on the deploying machine only: what this deployment carries, by name
    for _note in deploy_notes(
        SECRET_ENV, WITNESS_ENV, model=with_model(os.environ), evidence_lookups=with_evidence_lookups(os.environ),
    ):
        print(_note, file=sys.stderr)  # noqa: T201 - beside the output of `modal deploy`, never on stdout
WITNESS_WANTED = witness_is_wanted(is_local=modal.is_local(), secret_env=WITNESS_ENV, environ=os.environ)

if WITNESS_WANTED:

    @app.function(
        image=build_image(), secrets=[modal.Secret.from_dict(WITNESS_ENV)],
        schedule=modal.Period(hours=WITNESS_EVERY_HOURS), cpu=WITNESS_CPU_CORES, max_containers=1,
    )
    def witness_audit_head() -> str:
        """Every hour: is the head noted last time still at its place in the supplier's view?"""
        notes = DictNotes(modal.Dict.from_name(WITNESS_NOTES, create_if_missing=True))
        return run_witness(_supplier_connection, notes, os.environ)
