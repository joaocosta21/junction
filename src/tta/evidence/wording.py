"""The sentences of the evidence package, as templates. None is written by a model.

Every reason completes "No evidence was found on the web for product <id>: <reason>." The found sentence quotes
the page's own words, each inside “…” marks that `reading._clean` keeps the page from closing (security review
L2), and the pages escape them. It says "the manufacturer's page" only for a host listed for the brand.
"""

from __future__ import annotations

NOT_FOUND = "No evidence was found on the web for product {product_id}: {reason}."

NO_KEY = "no Context.dev key is set, so nothing was looked up"
NO_RECORDED_PAGE = (
    "no recorded page of this product is stored and no lookup is made on this link (no Context.dev key is set)"
)
NO_PAGE = "no manufacturer's page of this product was found"
# A page that is not kept: the reason is one of the lines below (`matching.why_not_this_product`). A page that may
# be a sibling of the product is dropped like any other: a false match is worse than a missing page.
OTHER_PRODUCT = "the page found (“{name}”) is not shown to be this product and was dropped: {why}"
BRAND_NOT_SHOWN = "the page does not show the brand “{brand}”"
NO_BRAND = "the product has no brand in Valio Aimo's data, so a page cannot be shown to be its maker's"
PERCENT_DIFFERS = "the page is for the {page} product; the product asked for is {ours}"
PERCENT_NOT_ON_PAGE = "the product asked for is {ours}; the page's product name states no percentage"
PERCENT_NOT_ON_PRODUCT = "the page is for a {page} product; the product asked for states no percentage"
MARK_NOT_ON_PAGE = "the product asked for is {mark}; the page does not say {mark}"
MARK_NOT_ON_PRODUCT = "the page says {mark}; the product asked for does not say {mark}"
FLAVOUR_DIFFERS = "the page's product name says {page}; the product asked for says {ours}"
NO_FLAVOUR = "no flavour"
PACK_DIFFERS = "the page is for the {page} pack; the product asked for is {ours}"
WORDS_ADDED = "the page's product name says {words}, which the product asked for does not"
TOO_LITTLE_OF_NAME = "the page's product name carries too little of the name of the product asked for"
NOTHING_TO_COMPARE = "the page's product name names no product"
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

# Who the page belongs to is said by the first words of `Evidence.sentence`, which every page that shows evidence
# prints: "The manufacturer's page" only when the page's host is one we list for the product's brand
# (`matching.BRAND_OWNER_HOSTS`); nobody checked who owns any other page (AP-4). There is no separate heading text
# here: a page's own heading must not say more than the sentence does.
PAGE_OWNER = "The manufacturer's page"
PAGE_UNCHECKED = "A web page whose owner was not checked,"
FOUND = "{page} “{name}” on {host} says: {parts}."
FOUND_NOTHING = "{page} “{name}” on {host} names no allergen in its text."
CONTAINS = "contains {terms}"
MAY_CONTAIN = "may contain {terms}"
FREE_FROM = "free from {terms}"
# Entries of the page's lists that could not be read (`reading._terms`): said on the card, never left out.
UNREAD_ENTRIES = "{count} of the entries the page lists could not be read and are not shown."


def not_found(product_id: str, reason: str) -> str:
    return NOT_FOUND.format(product_id=product_id, reason=reason)


def found(
    name: str, host: str, contains: tuple[str, ...], may_contain: tuple[str, ...], free_from: tuple[str, ...],
    *, is_owner_page: bool, unread: int = 0,
) -> str:
    page = PAGE_OWNER if is_owner_page else PAGE_UNCHECKED
    parts = [
        template.format(terms=", ".join(f"“{term}”" for term in terms))  # each term in marks it cannot close
        for template, terms in ((CONTAINS, contains), (MAY_CONTAIN, may_contain), (FREE_FROM, free_from))
        if terms
    ]
    template = FOUND if parts else FOUND_NOTHING
    said = template.format(page=page, name=name, host=host, parts="; ".join(parts))
    return f"{said} {UNREAD_ENTRIES.format(count=unread)}" if unread else said


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
PAGE_LISTS_NOTHING = "the page lists nothing under contains, may contain or free from, so it says nothing about it"
PAGE_UNREAD = "some of the page's words could not be read, so nothing is concluded about {allergen}"
PAGE_UNMATCHED = "the page's words could not be matched to this allergen (“{words}”), so nothing is read from them"
ALSO_FREE_FROM = " (it also says free from: “{words}”)"
# The reason a page adds for the person who signs. Stricter only: nothing a page says removes a doubt.
PAGE_NAMES_EXCLUDED = (
    "The page names {allergens}, which this order excludes: check the product before approving. "
    "What a page says can add a doubt and never removes one."
)
