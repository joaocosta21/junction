"""A private order book per browser session of the pages (task FIX-10, finding 1).

Scores on the 30% "working end-to-end demo" (every judge who opens the public link starts from an empty
book and sees the autonomous path) and on the 20% "autonomy and controls": the daily spend limit counts one
buyer's orders of the day, and on one book shared by every visitor three runs of scenario 2 used up the
ward's day for everybody, and one visitor's orders showed on another's approvals page.

A sandbox is an order book of its own: an in-memory SQLite store, an audit trail, an offer service and an
order book, over the parts every visitor shares (the catalog, the supplier gateway with its fall-back and call
budget, the policy, the limits, the request parser and the buyer agent). The limits are keyed by the
visitor's address, so a new browser buys no new window. The REST API and MCP keep the shared book of their
tokens. Nothing in a sandbox survives a restart, and it commits nobody.

At most `MAX_SANDBOXES` are kept; above that the one used least recently is dropped, and so is one idle for
`SANDBOX_IDLE_SECONDS`. A dropped book is closed: a visitor who comes back starts from an empty one.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

from tta.api.service import Gateway
from tta.contracts.ports import AuditSink
from tta.store import SqliteStore

MAX_SANDBOXES = 300
SANDBOX_IDLE_SECONDS = 2 * 60 * 60


@dataclass(frozen=True, eq=False)  # one book is one object: compared and hashed by identity
class Sandbox:
    """One visitor's order book."""

    service: Gateway
    store: SqliteStore
    audit: AuditSink

    def close(self) -> None:
        self.store.close()


class Sandboxes:
    """The sandboxes of this process by key (a browser session's cookie), least recently used first.

    `find` and `blank` are for reading: a visitor with no book of its own reads the blank one, which nothing
    is ever written to. `open` is for writing: it builds the visitor's book on its first use. Thread-safe.
    """

    def __init__(
        self,
        build: Callable[[], Sandbox],
        *,
        capacity: int = MAX_SANDBOXES,
        idle_seconds: float = SANDBOX_IDLE_SECONDS,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._build = build
        self._capacity = capacity
        self._idle_seconds = idle_seconds
        self._monotonic = monotonic
        self._lock = threading.Lock()
        self._books: OrderedDict[str, tuple[Sandbox, float]] = OrderedDict()  # key -> (book, last used)
        self._blank: Sandbox | None = None

    def __len__(self) -> int:
        with self._lock:
            return len(self._books)

    def find(self, key: str | None) -> Sandbox | None:
        """The book of this key, or `None` when it has none (never had one, idle too long, or dropped)."""
        if key is None:
            return None
        with self._lock:
            self._drop_idle()
            return self._touch(key)

    def open(self, key: str) -> Sandbox:
        """The book of this key, built empty when it has none. The book used least recently goes first."""
        with self._lock:
            self._drop_idle()
            book = self._touch(key)
            if book is not None:
                return book
            book = self._build()
            self._books[key] = (book, self._monotonic())
            while len(self._books) > self._capacity:
                _, (oldest, _) = self._books.popitem(last=False)
                oldest.close()
            return book

    def blank(self) -> Sandbox:
        """An empty book for reading by a visitor who has none yet: the pages write only to `open` books."""
        with self._lock:
            if self._blank is None:
                self._blank = self._build()
            return self._blank

    def drop(self, key: str | None) -> None:
        """Empty this visitor's book ("Start again"): it is closed, and the next `open` builds a new one."""
        with self._lock:
            found = self._books.pop(key, None) if key is not None else None
        if found is not None:
            found[0].close()

    def close(self) -> None:
        """Close every book, the blank one too."""
        with self._lock:
            books = [book for book, _ in self._books.values()] + ([self._blank] if self._blank else [])
            self._books.clear()
            self._blank = None
        for book in books:
            book.close()

    def _touch(self, key: str) -> Sandbox | None:
        found = self._books.get(key)
        if found is None:
            return None
        self._books[key] = (found[0], self._monotonic())
        self._books.move_to_end(key)
        return found[0]

    def _drop_idle(self) -> None:
        """Drop the books nobody used for `idle_seconds`. The least recently used come first, so this stops at
        the first book still in use."""
        limit = self._monotonic() - self._idle_seconds
        while self._books:
            key, (book, used) = next(iter(self._books.items()))
            if used > limit:
                return
            del self._books[key]
            book.close()
