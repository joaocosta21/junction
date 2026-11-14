"""The sentences of the evidence package, as templates. None is written by a model.

Every reason completes "No evidence was found on the web for product <id>: <reason>." The found sentence quotes
the page's own words, which the pages escape.
"""

from __future__ import annotations

NOT_FOUND = "No evidence was found on the web for product {product_id}: {reason}."

NO_KEY = "no Context.dev key is set, so nothing was looked up"
NO_PAGE = "no manufacturer's page of this product was found"
OTHER_PRODUCT = "the page found is for another product (“{name}”), so it was dropped"
NO_NAME_ON_PAGE = "the page found does not show the product's name, so it could not be checked and was dropped"
NO_SOURCE = "the answer names no page it read"
FAILED_OUTPUT = "the search service reported that this answer failed"
PARTIAL = "the research stopped before it was complete"
UNREADABLE = "the answer could not be read"
STORED_UNREADABLE = "the stored result could not be read"
NO_ANSWER_IN_TIME = "the web search did not answer in time"
UNREACHABLE = "the web search service could not be reached"
KEY_REFUSED = "the search service refused the key"
NO_CREDITS = "the search service has no credits left"
OUT_OF_TIME = "the research ran out of time"
RATE_LIMITED = "the search service's rate limit was reached"
ANSWERED_STATUS = "the search service answered HTTP {status}"
BUDGET_SPENT = "this gateway's limit of {limit} web lookups is spent"
NOT_IN_CATALOG = "the product is not in the catalog"
TOO_MANY = "at most {limit} products are looked up for one approval"
LOOKUP_FAILED = "the lookup failed in the gateway"

FOUND = "The page “{name}” on {host} says: {parts}."
FOUND_NOTHING = "The page “{name}” on {host} names no allergen in its text."
CONTAINS = "contains {terms}"
MAY_CONTAIN = "may contain {terms}"
FREE_FROM = "free from {terms}"


def not_found(product_id: str, reason: str) -> str:
    return NOT_FOUND.format(product_id=product_id, reason=reason)


def found(
    name: str, host: str, contains: tuple[str, ...], may_contain: tuple[str, ...], free_from: tuple[str, ...]
) -> str:
    parts = [
        template.format(terms=", ".join(terms))
        for template, terms in ((CONTAINS, contains), (MAY_CONTAIN, may_contain), (FREE_FROM, free_from))
        if terms
    ]
    if not parts:
        return FOUND_NOTHING.format(name=name, host=host)
    return FOUND.format(name=name, host=host, parts="; ".join(parts))
