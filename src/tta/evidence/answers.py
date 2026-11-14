"""The Context.dev Answers endpoint, asked for a product's manufacturer page (task S2, docs/CONTEXTDEV.md).

`POST https://api.context.dev/v1/web/answers` researches a task on the live web and returns `json_content` in the
shape of our `json_format` example, plus `sources`, the pages it read (https://docs.context.dev/answers/overview.md).
The task carries the product's English and Finnish names and its brand, and nothing about the buyer: no profile,
exclusion, quantity, date or id. The key goes into the `Authorization` header when a request is sent, nowhere else.
Every failure is an `EvidenceUnavailable` with a plain reason, never an httpx error and never the service's own text.
"""

from __future__ import annotations

import json
import threading
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from tta.config import Settings
from tta.contracts.common import JsonDict
from tta.contracts.product import Product
from tta.evidence import wording

ANSWERS_URL = "https://api.context.dev/v1/web/answers"
# `ultra` reads pages; `fast` answers from search snippets and returned another product's page in our first
# trials (request log in docs/CONTEXTDEV.md). Ultra costs 100 credits a request, fast 10.
MODE = "ultra"
# Research stops at this deadline and answers 408 ("fail"): a partial answer is never taken as evidence.
DEADLINE_MILLISECONDS = 40_000
HTTP_TIMEOUT_SECONDS = 50.0  # longer than the deadline, as the documentation asks
CONNECT_TIMEOUT_SECONDS = 5.0
MAX_BODY_BYTES = 1_000_000  # the answers recorded on 14 Nov are under 1 kB
# Lookups one client may send in its process: a public demo cannot spend the team's credits without bound.
DEFAULT_MAX_CALLS = 40
MAX_NAME_LENGTH = 120
USER_AGENT = "tta-gateway/0.1"
OK = 200
# The example answer Context.dev fills in; it is an example object, not a JSON Schema (answers/answer-shape.md).
JSON_FORMAT: JsonDict = {
    "page_found": True,
    "source_url": "",
    "page_title": "",
    "product_name_on_page": "",
    "contains": [""],
    "may_contain": [""],
    "free_from": [""],
}
TASK = (
    "Find the official product page of the manufacturer or brand owner for the food product '{name}'{details}, "
    "and read it. Report only what that page states. product_name_on_page and page_title: exactly as the page "
    "shows them. source_url: the address of that page. contains: each allergen the page names in its allergen "
    "information or marks in the ingredient list (for example in bold). may_contain: each allergen of a 'may "
    "contain' or traces statement. free_from: each allergen the page says the product is free from (for example "
    "gluten-free, milk-free, lactose-free). Use the page's own words. Leave a list empty when the page says "
    "nothing for it. Set page_found to false when no page of this product is found."
)
_REFUSALS = {
    401: wording.KEY_REFUSED,
    402: wording.NO_CREDITS,
    403: wording.KEY_REFUSED,
    408: wording.OUT_OF_TIME,
    429: wording.RATE_LIMITED,
    504: wording.OUT_OF_TIME,
}


class EvidenceUnavailable(Exception):
    """No answer could be had. `reason` completes "No evidence was found on the web for product …: <reason>"."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class AnswerRecord:
    """One answer of Context.dev as it was received: the product, when, what was sent and the body."""

    product_id: str
    retrieved_at: datetime
    request: JsonDict
    body: JsonDict

    def to_json(self) -> JsonDict:
        return {
            "product_id": self.product_id, "retrieved_at": self.retrieved_at.isoformat(),
            "endpoint": f"POST {ANSWERS_URL}", "request": self.request, "response": self.body,
        }

    @classmethod
    def from_json(cls, data: Any) -> AnswerRecord:
        """Raises `ValueError` when the stored data is not a record."""
        if not isinstance(data, dict):
            raise ValueError("a stored answer is a JSON object")
        product_id, retrieved_at = data.get("product_id"), data.get("retrieved_at")
        request, body = data.get("request"), data.get("response")
        if not isinstance(product_id, str) or not isinstance(retrieved_at, str):
            raise ValueError("a stored answer names its product and time")
        if not isinstance(request, dict) or not isinstance(body, dict):
            raise ValueError("a stored answer holds its request and response")
        moment = datetime.fromisoformat(retrieved_at)
        if moment.tzinfo is None:
            raise ValueError("a stored answer's time carries its offset")
        return cls(product_id=product_id, retrieved_at=moment, request=request, body=body)


def _plain(name: str | None) -> str | None:
    """A name as text for the task: no control characters, no quotation marks, bounded."""
    if not name:
        return None
    kept = "".join(" " if unicodedata.category(c).startswith("C") else c for c in name if c not in "'\"`")
    folded = " ".join(kept.split())[:MAX_NAME_LENGTH]
    return folded or None


def answer_request(product: Product) -> JsonDict:
    """The body sent for one product. It is built from the product alone."""
    name = _plain(product.name_en) or _plain(product.name_fi) or product.id
    finnish, brand = _plain(product.name_fi), _plain(product.brand)
    details = [f"Finnish name '{finnish}'"] if finnish and finnish != name else []
    details += [f"brand '{brand}'"] if brand else []
    task = TASK.format(name=name, details=f" ({', '.join(details)})" if details else "")
    return {
        "mode": MODE, "task": task, "json_format": JSON_FORMAT,
        "timeoutOpts": {"milliseconds": DEADLINE_MILLISECONDS, "behavior": "fail"},
    }


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AnswersClient:
    """Asks Context.dev's Answers endpoint about one product at a time. Raises `EvidenceUnavailable` only."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
        now: Callable[[], datetime] = _utc_now,
        max_calls: int = DEFAULT_MAX_CALLS,
    ) -> None:
        self._settings = settings
        self._now = now
        self._max_calls = max_calls
        self._calls = 0
        self._lock = threading.Lock()
        timeout = httpx.Timeout(HTTP_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS)
        self._http = httpx.Client(timeout=timeout, transport=transport, headers={"User-Agent": USER_AGENT})

    def ask(self, product: Product) -> AnswerRecord:
        secret = self._settings.context_dev_api_key
        if not self._settings.has_context_dev_key or secret is None:
            raise EvidenceUnavailable(wording.NO_KEY)
        self._spend_one_call()
        body = answer_request(product)
        headers = {"Authorization": f"Bearer {secret.get_secret_value()}"}
        try:
            response = self._http.post(ANSWERS_URL, json=body, headers=headers)
        except httpx.TimeoutException as error:
            raise EvidenceUnavailable(wording.NO_ANSWER_IN_TIME) from error
        except httpx.HTTPError as error:
            raise EvidenceUnavailable(wording.UNREACHABLE) from error
        return AnswerRecord(product_id=product.id, retrieved_at=self._now(), request=body, body=_body(response))

    def close(self) -> None:
        self._http.close()

    def _spend_one_call(self) -> None:
        with self._lock:
            if self._calls >= self._max_calls:
                raise EvidenceUnavailable(wording.BUDGET_SPENT.format(limit=self._max_calls))
            self._calls += 1


def _body(response: httpx.Response) -> JsonDict:
    """The answer's JSON object. A refusal is named by its status; the service's own message is not repeated."""
    if response.status_code != OK:
        reason = _REFUSALS.get(response.status_code, wording.ANSWERED_STATUS.format(status=response.status_code))
        raise EvidenceUnavailable(reason)
    if len(response.content) > MAX_BODY_BYTES:
        raise EvidenceUnavailable(wording.UNREADABLE)
    try:
        body = json.loads(response.content)
    except ValueError as error:
        raise EvidenceUnavailable(wording.UNREADABLE) from error
    if not isinstance(body, dict):
        raise EvidenceUnavailable(wording.UNREADABLE)
    return body
