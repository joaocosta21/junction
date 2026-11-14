"""The database on Modal: SQLite works on the container's own disk, a whole copy is kept on the Volume (task T14).

The copy is taken with SQLite's backup API, so it is consistent while the gateway's connection stays open in WAL
mode; it replaces the kept copy in one step; then the Volume is committed. No test needs Modal: the commit is a
stand-in that counts.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

WAIT_SECONDS = 5.0


class Commits:
    """Stands in for `volume.commit`: counts, and can fail a given number of times first."""

    def __init__(self, failures: int = 0) -> None:
        self.count = 0
        self._failures = failures

    def __call__(self) -> None:
        if self._failures:
            self._failures -= 1
            raise RuntimeError("the volume could not be committed")
        self.count += 1


@pytest.fixture
def working(tmp_path: Path) -> Path:
    return tmp_path / "local" / "tta.sqlite3"


@pytest.fixture
def kept(tmp_path: Path) -> Path:
    path = tmp_path / "volume" / "tta.sqlite3"
    path.parent.mkdir()
    return path


@pytest.fixture
def writer(working: Path) -> Iterator[sqlite3.Connection]:
    """A connection held open in WAL mode, as the gateway's store holds its own."""
    working.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(working, check_same_thread=False)
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA wal_autocheckpoint = 0")  # rows stay in the WAL file, as between checkpoints
    connection.execute("CREATE TABLE orders (id TEXT PRIMARY KEY)")
    connection.commit()
    yield connection
    connection.close()


@pytest.fixture
def make_saver(modal_app: ModuleType, working: Path, kept: Path) -> Iterator[Any]:
    """Savers over `working` and `kept`, each closed at the end of the test."""
    made: list[Any] = []

    def make(commits: Commits, **options: Any) -> Any:
        saver = modal_app.DatabaseSaver(working, kept, commits, **options)
        made.append(saver)
        return saver

    yield make
    for saver in made:
        saver.close()


def _add(connection: sqlite3.Connection, order_id: str) -> None:
    connection.execute("INSERT INTO orders VALUES (?)", (order_id,))
    connection.commit()


def _orders(path: Path) -> list[str]:
    connection = sqlite3.connect(path)
    try:
        return [row[0] for row in connection.execute("SELECT id FROM orders ORDER BY id")]
    finally:
        connection.close()


# --- restore at start -------------------------------------------------------------------------------------------


def test_the_kept_copy_is_put_on_local_disk_at_start(modal_app: ModuleType, kept: Path, working: Path) -> None:
    connection = sqlite3.connect(kept)
    connection.execute("CREATE TABLE orders (id TEXT PRIMARY KEY)")
    connection.execute("INSERT INTO orders VALUES ('ord_1')")
    connection.commit()
    connection.close()

    assert modal_app.restore(working, kept) is True
    assert _orders(working) == ["ord_1"]


def test_without_a_kept_copy_the_gateway_starts_on_an_empty_database(
    modal_app: ModuleType, kept: Path, working: Path
) -> None:
    assert modal_app.restore(working, kept) is False
    assert not working.exists()
    assert working.parent.is_dir()


# --- saving after a change --------------------------------------------------------------------------------------


def test_a_change_is_copied_whole_and_committed(writer: sqlite3.Connection, kept: Path, make_saver: Any) -> None:
    commits = Commits()
    saver = make_saver(commits)
    _add(writer, "ord_1")

    assert saver.save_if_changed() is True
    assert commits.count == 1
    assert _orders(kept) == ["ord_1"]  # the rows still in the WAL file are in the copy
    assert sorted(path.name for path in kept.parent.iterdir()) == ["tta.sqlite3"]  # no part-written file left


def test_no_change_means_no_copy_and_no_commit(writer: sqlite3.Connection, make_saver: Any) -> None:
    commits = Commits()
    saver = make_saver(commits)
    saver.save_if_changed()

    assert saver.save_if_changed() is False
    assert commits.count == 1


def test_each_later_change_is_copied_again(writer: sqlite3.Connection, kept: Path, make_saver: Any) -> None:
    commits = Commits()
    saver = make_saver(commits)
    saver.save_if_changed()
    _add(writer, "ord_2")

    assert saver.save_if_changed() is True
    assert commits.count == 2
    assert _orders(kept) == ["ord_2"]


def test_before_the_gateway_made_its_database_there_is_nothing_to_save(kept: Path, make_saver: Any) -> None:
    commits = Commits()
    saver = make_saver(commits)

    assert saver.save_if_changed() is False
    assert saver.save() is False
    assert commits.count == 0
    assert not kept.exists()


def test_a_failed_commit_is_logged_and_tried_again_at_the_next_save(
    writer: sqlite3.Connection, make_saver: Any, caplog: pytest.LogCaptureFixture
) -> None:
    commits = Commits(failures=1)
    saver = make_saver(commits)
    _add(writer, "ord_1")

    with caplog.at_level(logging.ERROR):
        assert saver.save_if_changed() is False
    assert "could not be saved to the Volume" in caplog.text
    assert saver.save_if_changed() is True  # nothing changed since, and it is tried again
    assert commits.count == 1


def test_a_database_that_cannot_be_read_is_logged_and_not_copied(
    working: Path, kept: Path, make_saver: Any, caplog: pytest.LogCaptureFixture
) -> None:
    working.parent.mkdir(parents=True)
    working.write_text("not a database " * 20, encoding="utf-8")
    commits = Commits()

    with caplog.at_level(logging.ERROR):
        assert make_saver(commits).save_if_changed() is False
    assert "could not be watched for changes" in caplog.text
    assert commits.count == 0
    assert not kept.exists()


def test_after_close_the_next_check_copies_once_more(writer: sqlite3.Connection, make_saver: Any) -> None:
    commits = Commits()
    saver = make_saver(commits)
    saver.save_if_changed()

    saver.close()

    assert saver.save_if_changed() is True
    assert commits.count == 2


def test_the_saver_thread_saves_soon_after_it_is_woken(writer: sqlite3.Connection, kept: Path, make_saver: Any) -> None:
    commits = Commits()
    saver = make_saver(commits, delay_seconds=0.01)
    saver.start()
    _add(writer, "ord_1")

    saver.wake()

    deadline = time.monotonic() + WAIT_SECONDS
    while commits.count == 0 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert commits.count == 1
    assert _orders(kept) == ["ord_1"]


# --- the ASGI wrapper -------------------------------------------------------------------------------------------


class Saver:
    """Stands in for `DatabaseSaver`: records what the wrapper asked of it, in order."""

    def __init__(self, events: list[str]) -> None:
        self.events = events

    def wake(self) -> None:
        self.events.append("wake")

    def save(self) -> bool:
        self.events.append("save")
        return True


def _serve(modal_app: ModuleType, app: Any, scope: dict[str, Any], events: list[str]) -> None:
    messages = iter([{"type": "http.request", "body": b"", "more_body": False}])

    async def receive() -> dict[str, Any]:
        return next(messages, {"type": "http.disconnect"})

    async def send(message: dict[str, Any]) -> None:
        events.append(f"sent {message['type']}")

    asyncio.run(modal_app.SaveAfterRequests(app, Saver(events))(scope, receive, send))


async def _ok(scope: dict[str, Any], receive: Any, send: Any) -> None:
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def test_the_saver_is_woken_after_each_request_has_been_answered(modal_app: ModuleType) -> None:
    events: list[str] = []

    _serve(modal_app, _ok, {"type": "http", "method": "GET", "path": "/"}, events)

    assert events == ["sent http.response.start", "sent http.response.body", "wake"]


def test_a_request_that_fails_still_wakes_the_saver(modal_app: ModuleType) -> None:
    events: list[str] = []

    async def broken(scope: dict[str, Any], receive: Any, send: Any) -> None:
        raise RuntimeError("the application failed")

    with pytest.raises(RuntimeError, match="the application failed"):
        _serve(modal_app, broken, {"type": "http", "method": "POST", "path": "/v1/orders"}, events)
    assert events == ["wake"]


def test_the_last_save_is_made_before_the_shutdown_is_reported(modal_app: ModuleType) -> None:
    events: list[str] = []

    async def lifespan(scope: dict[str, Any], receive: Any, send: Any) -> None:
        await send({"type": "lifespan.startup.complete"})
        await send({"type": "lifespan.shutdown.complete"})

    _serve(modal_app, lifespan, {"type": "lifespan"}, events)

    assert events == ["sent lifespan.startup.complete", "save", "sent lifespan.shutdown.complete"]
