"""One Context.dev answer read into `Evidence`: validated, bounded, matched against the product (task S2).

Web content is untrusted input. It is read as data only: never executed, never handed to a model. Each text is
stripped of control characters and bounded in size; a link is kept only when it is a plain http(s) address that
the research itself read; a page whose product name does not name this product is dropped. The hash is SHA-256
over the canonical JSON of `json_content` exactly as Context.dev returned it, so a stored answer can be checked
against the audit event that cites it.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any
from urllib.parse import urlsplit

from tta.contracts.order import Evidence
from tta.contracts.product import Product
from tta.evidence import wording
from tta.evidence.answers import AnswerRecord
from tta.evidence.matching import is_brand_owner_page, names_match

MAX_TEXT_LENGTH = 200  # a page title or a product name
MAX_TERM_LENGTH = 80  # one allergen term; a longer one is dropped, not cut, so its meaning is not changed
MAX_TERMS = 20  # per list
MAX_URL_LENGTH = 500
WEB_SCHEMES = ("https", "http")
WWW = "www."


def _clean(text: Any) -> str | None:
    """Text without control or format characters (a right-to-left override among them), whitespace folded."""
    if not isinstance(text, str):
        return None
    kept = "".join(c for c in text if not unicodedata.category(c).startswith("C"))
    folded = " ".join(kept.split())
    return folded or None


def _bounded(text: Any) -> str | None:
    cleaned = _clean(text)
    return cleaned[:MAX_TEXT_LENGTH] if cleaned else None


def _terms(values: Any) -> tuple[str, ...]:
    if not isinstance(values, list):
        return ()
    cleaned = (_clean(value) for value in values)
    return tuple(term for term in cleaned if term and len(term) <= MAX_TERM_LENGTH)[:MAX_TERMS]


def _link(value: Any, sources: list[Any]) -> str | None:
    """The page's address, when it is a plain web address of a page the research read."""
    if not isinstance(value, str) or not value or len(value) > MAX_URL_LENGTH or value not in sources:
        return None
    parts = urlsplit(value)
    if parts.scheme not in WEB_SCHEMES or not parts.hostname or parts.username or parts.password:
        return None
    return value


def _host(url: str) -> str:
    host = urlsplit(url).hostname or url
    return host.removeprefix(WWW)


def content_hash(content: dict[str, Any]) -> str:
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _missing(record: AnswerRecord, reason: str) -> Evidence:
    return Evidence(
        product_id=record.product_id, found=False, retrieved_at=record.retrieved_at,
        sentence=wording.not_found(record.product_id, reason),
    )


def _failure(body: dict[str, Any]) -> str | None:
    """Why the answer as a whole cannot be used. A 200 can carry a failed or partial output."""
    if body.get("success") is False:
        return wording.FAILED_OUTPUT
    if body.get("partial") is True:
        return wording.PARTIAL
    if not isinstance(body.get("json_content"), dict) or not isinstance(body.get("sources"), list):
        return wording.UNREADABLE
    return None


def read_answer(record: AnswerRecord, product: Product) -> Evidence:
    """The evidence in one answer for one product, or why there is none."""
    body = record.body
    failure = _failure(body)
    if failure is not None:
        return _missing(record, failure)
    content: dict[str, Any] = body["json_content"]
    if content.get("page_found") is not True:
        return _missing(record, wording.NO_PAGE)
    url = _link(content.get("source_url"), body["sources"])
    if url is None:
        return _missing(record, wording.NO_SOURCE)
    name, title = _bounded(content.get("product_name_on_page")), _bounded(content.get("page_title"))
    if name is None:
        return _missing(record, wording.NO_NAME_ON_PAGE)
    if not names_match(name, title, url, product):
        return _missing(record, wording.OTHER_PRODUCT.format(name=name))
    contains, may_contain = _terms(content.get("contains")), _terms(content.get("may_contain"))
    free_from = _terms(content.get("free_from"))
    return Evidence(
        product_id=record.product_id, found=True, source_url=url, page_title=title, product_name_on_page=name,
        contains=contains, may_contain=may_contain, free_from=free_from, retrieved_at=record.retrieved_at,
        content_hash=content_hash(content),
        sentence=wording.found(
            name, _host(url), contains, may_contain, free_from, is_owner_page=is_brand_owner_page(url, product)
        ),
    )
