"""The sentences of the evidence package, as templates. None is written by a model.

Every reason completes "No evidence was found on the web for product <id>: <reason>." The found sentence quotes
the page's own words, which the pages escape. It says "the manufacturer's page" only for a host listed for the brand.
"""

from __future__ import annotations

NOT_FOUND = "No evidence was found on the web for product {product_id}: {reason}."

NO_KEY = "no Context.dev key is set, so nothing was looked up"
NO_RECORDED_PAGE = "no recorded page of this product is stored and no Context.dev key is set, so nothing was looked up"
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
COUNT_UNREADABLE = "the count of web lookups already made could not be read, so none was made"
NOT_IN_CATALOG = "the product is not in the catalog"
TOO_MANY = "at most {limit} products are looked up for one approval"
LOOKUP_FAILED = "the lookup failed in the gateway"
BATCH_CALL_FAILED = "the batch call for this product failed ({error})"

# The heading of the evidence on an approval card (AP-4). "Manufacturer's page" is said only when the page's host is
# one we list for the product's brand (`matching.BRAND_OWNER_HOSTS`); nobody checked who owns any other page.
HEADING_OWNER = "Manufacturer's page, not Valio Aimo data"
HEADING_UNCHECKED = "A web page that names this product, not Valio Aimo data (its owner was not checked)"
PAGE_OWNER = "The manufacturer's page"
PAGE_UNCHECKED = "A web page whose owner was not checked,"
FOUND = "{page} “{name}” on {host} says: {parts}."
FOUND_NOTHING = "{page} “{name}” on {host} names no allergen in its text."
CONTAINS = "contains {terms}"
MAY_CONTAIN = "may contain {terms}"
FREE_FROM = "free from {terms}"


def not_found(product_id: str, reason: str) -> str:
    return NOT_FOUND.format(product_id=product_id, reason=reason)


def heading(is_owner_page: bool) -> str:
    return HEADING_OWNER if is_owner_page else HEADING_UNCHECKED


def found(
    name: str, host: str, contains: tuple[str, ...], may_contain: tuple[str, ...], free_from: tuple[str, ...],
    *, is_owner_page: bool,
) -> str:
    page = PAGE_OWNER if is_owner_page else PAGE_UNCHECKED
    parts = [
        template.format(terms=", ".join(terms))
        for template, terms in ((CONTAINS, contains), (MAY_CONTAIN, may_contain), (FREE_FROM, free_from))
        if terms
    ]
    if not parts:
        return FOUND_NOTHING.format(page=page, name=name, host=host)
    return FOUND.format(page=page, name=name, host=host, parts="; ".join(parts))


# --- what the page answers for each allergen the order excludes (AP-9, `alignment.py`) ----------------------------

ASKED = "Asked about {allergen}: Valio Aimo's data {valio}; {page}."
VALIO_STATES_NOTHING = "states nothing"
VALIO_UNDECLARED = "says undeclared"
VALIO_NOT_RULED_OUT = "does not rule it out"
VALIO_CONTAINS = "says it contains it"
VALIO_FREE_FROM = "says free from"
PAGE_CONTAINS = "the page says it contains it, in its words “{words}”"
PAGE_MAY_CONTAIN = "the page says it may contain it, in its words “{words}”"
PAGE_OATS = "the page names oats (“{words}”) and does not say gluten-free"
PAGE_FREE_FROM = "the page says free from, in its words “{words}”"
PAGE_NOT_NAMED = "the page does not name it"
PAGE_UNMATCHED = "the page's words could not be matched to this allergen (“{words}”), so nothing is read from them"
ALSO_FREE_FROM = " (it also says free from: “{words}”)"
# The reason a page adds for the person who signs. Stricter only: nothing a page says removes a doubt.
PAGE_NAMES_EXCLUDED = (
    "The page names {allergens}, which this order excludes: check the product before approving. "
    "What a page says can add a doubt and never removes one."
)
