"""One Context.dev answer read into `Evidence`: validated, bounded, matched against the product (task S2).

Web content is untrusted input. It is read as data only: never executed, never handed to a model. Each text is
stripped of control characters, has its double quotation marks made single (it is shown inside “…”) and is
bounded in size; a link is kept only when it is a plain http(s) address that
the research itself read; a page whose product name does not name this product is dropped. The hash is SHA-256
over the canonical JSON of `json_content` exactly as Context.dev returned it, so a stored answer can be checked
against the audit event that cites it.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any
from urllib.parse import urlsplit

from tta.contracts.order import Evidence
from tta.contracts.product import Product
from tta.evidence import wording
from tta.evidence.answers import AnswerRecord
from tta.evidence.matching import is_brand_owner_page, why_not_this_product

MAX_TEXT_LENGTH = 200  # a page title or a product name
# One allergen term. A longer entry is never cut (its meaning would change) and never dropped without a trace: it
# is split into its parts and each part is read; a part that is still longer is counted as not read (S2).
MAX_TERM_LENGTH = 80
MAX_TERMS = 20  # per list; the entries past it are counted as not read
# Where a long entry is split: commas, semicolons, and the word "and" (Finnish "ja") between spaces.
_PARTS = re.compile(r"\s*[,;]\s*(?:(?:and|ja)\s+)?|\s+(?:and|ja)\s+", re.IGNORECASE)
MAX_URL_LENGTH = 500
# Every mark a reader could take for the end of a quotation. The same set as `tta.audit.phrases.DOUBLE_QUOTES`
# (tests/evidence checks they agree); written here again because the batch's container holds this package without
# the libraries the audit package's own imports need.
DOUBLE_QUOTES = '"“”„‟«»＂'
TO_SINGLE_QUOTES = str.maketrans(dict.fromkeys(DOUBLE_QUOTES, "'"))
WEB_SCHEMES = ("https", "http")
WWW = "www."


def _clean(text: Any) -> str | None:
    """Text of a page, fit for a sentence the gateway shows: no control or format character (a right-to-left
    override among them), one line, and every double quotation mark a single one, so that words quoted inside
    “…” cannot close the quotation and go on in the gateway's voice."""
    if not isinstance(text, str):
        return None
    kept = "".join(c for c in text.translate(TO_SINGLE_QUOTES) if not unicodedata.category(c).startswith("C"))
    folded = " ".join(kept.split())
    return folded or None


def _bounded(text: Any) -> str | None:
    cleaned = _clean(text)
    return cleaned[:MAX_TEXT_LENGTH] if cleaned else None


def _parts(entry: str) -> tuple[str, ...]:
    """One entry as terms, in the page's own words: itself when it is short, else its parts."""
    if len(entry) <= MAX_TERM_LENGTH:
        return (entry,)
    return tuple(part for part in (piece.strip() for piece in _PARTS.split(entry)) if part)


def _terms(values: Any) -> tuple[tuple[str, ...], int]:
    """(the terms of one list, how many of its entries could not be read). An entry that is no text, a part of a
    long entry that is itself too long, and every term past `MAX_TERMS` are counted, so that whoever answers an
    allergen from these terms knows the list is not whole. An empty entry and a missing list are nothing to read."""
    if values is None:
        return (), 0
    entries = values if isinstance(values, list) else [values]  # one text instead of a list is read as one entry
    terms: list[str] = []
    unread = 0
    for entry in entries:
        if entry is None or entry == "":
            continue
        cleaned = _clean(entry)
        if cleaned is None:
            unread += 0 if isinstance(entry, str) else 1  # text of control characters and spaces only says nothing
            continue
        parts = _parts(cleaned)
        terms += [part for part in parts if len(part) <= MAX_TERM_LENGTH]
        unread += sum(1 for part in parts if len(part) > MAX_TERM_LENGTH)
    return tuple(terms[:MAX_TERMS]), unread + max(0, len(terms) - MAX_TERMS)


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
    return read_page(record, product)[0]


def read_page(record: AnswerRecord, product: Product) -> tuple[Evidence, int]:
    """(the evidence, how many entries of the page's lists could not be read). The count goes to
    `alignment.with_answers`: with any entry unread, no allergen is answered "the page does not name it"."""
    body = record.body
    failure = _failure(body)
    if failure is not None:
        return _missing(record, failure), 0
    content: dict[str, Any] = body["json_content"]
    if content.get("page_found") is not True:
        return _missing(record, wording.NO_PAGE), 0
    url = _link(content.get("source_url"), body["sources"])
    if url is None:
        return _missing(record, wording.NO_SOURCE), 0
    name, title = _bounded(content.get("product_name_on_page")), _bounded(content.get("page_title"))
    if name is None:
        return _missing(record, wording.NO_NAME_ON_PAGE), 0
    (contains, lost_1), (may_contain, lost_2) = _terms(content.get("contains")), _terms(content.get("may_contain"))
    free_from, lost_3 = _terms(content.get("free_from"))
    unread = lost_1 + lost_2 + lost_3
    why_not = why_not_this_product(name, title, url, product, free_from)
    if why_not is not None:
        return _missing(record, wording.OTHER_PRODUCT.format(name=name, why=why_not)), 0
    return Evidence(
        product_id=record.product_id, found=True, source_url=url, page_title=title, product_name_on_page=name,
        contains=contains, may_contain=may_contain, free_from=free_from, retrieved_at=record.retrieved_at,
        content_hash=content_hash(content),
        sentence=wording.found(
            name, _host(url), contains, may_contain, free_from, is_owner_page=is_brand_owner_page(url, product),
            unread=unread,
        ),
    ), unread
