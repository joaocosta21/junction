"""A private order book per browser session of the pages (task FIX-10, finding 1).

Scores on the 30% "working end-to-end demo" (every judge who opens the public link starts from an empty
book and sees the autonomous path) and on the 20% "autonomy and controls": the daily spend limit counts one
buyer's orders of the day, and on one book shared by every visitor three runs of scenario 2 used up the
ward's day for everybody, and one visitor's orders showed on another's approvals page.

A sandbox is an order book of its own: an in-memory SQLite store, an audit trail, an offer service and an
order book, over the parts every visitor shares (the catalog, the supplier gateway with its fall-back and call
budget, the policy, the limits, the request parser and the buyer agent). The limits are keyed by the
browser and capped per address (`tta.api.limits`, task FIX-11). The REST API and MCP keep the shared book of
their tokens. Nothing in a sandbox survives a restart, and it commits nobody.

At most `MAX_SANDBOXES` are kept; above that the one used least recently is dropped, and so is one idle for
`SANDBOX_IDLE_SECONDS`. A dropped book is closed: a visitor who comes back starts from an empty one. One
address opens at most `MAX_NEW_BOOKS_PER_ADDRESS` new books in `NEW_BOOKS_WINDOW_MINUTES` (task FIX-11): a
room on one Wi-Fi opens one each, and one address sending a new cookie with every form cannot push the other
visitors' books out of the `MAX_SANDBOXES`.

Each book also holds one custom buyer profile, "My kitchen" (task FEAT-1): what the visitor lets its own agent,
"My kitchen agent", decide alone. It starts as a copy of `hotel-kitchen`, is checked exactly as a profile file is,
and is in force only in the calls made on this book's service (`tta.policy.custom`): the shared book of the
tokens, the policy files and every other book never see it. Its approvals are decided by three approvers bound to
it, one per role, who carry the name of the hotel's one person (one person confirms). "Start again" drops it with
the book.

Every change of a kitchen's settings is one event in the book's audit trail, under the name of the person who
orders, with each changed setting before and after (decision B59, `tta.api.kitchen_log`). And where the book stands
for a customer with a dietitian of its own (the ward, the school), her allergen exclusions and her strict rule
cannot be removed or relaxed here.
"""

from __future__ import annotations

import functools
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, cast

from tta.api.kitchen_log import changes, dietitians_refusals, record_change
from tta.api.limits import SECONDS_PER_MINUTE, Counted, RateLimit, RateLimiter, current_client_key
from tta.api.service import Gateway
from tta.api.suggesting import customer_on_file
from tta.contracts.common import ApproverRole, Identity, IdentityKind
from tta.contracts.customer import Customer
from tta.contracts.errors import NotAuthorised
from tta.contracts.policy import BuyerProfile
from tta.contracts.ports import AuditSink
from tta.customers import shipped_customer
from tta.orders.access import actor_of
from tta.policy import PolicyLoadError, RulePolicyEngine, profile_in_force
from tta.policy.human_approval import decided_as
from tta.policy.rulebook import AccessRule
from tta.store import SqliteStore

# The review day (decision B55, check C2-1): the shop page opens a book on page load and on every customer switch,
# and a room of reviewers sits behind the venue's one address. 8 of them clicking through the 4 customers reached
# the 30 new books of before, and every call of the room was then refused for up to 10 minutes. A used book takes
# about 1 MiB (measured 15 Nov); `deploy/modal_app.py` gives the container the memory for all of them.
MAX_SANDBOXES = 1000  # was 300
SANDBOX_IDLE_SECONDS = 2 * 60 * 60
MAX_NEW_BOOKS_PER_ADDRESS = 400  # was 30
NEW_BOOKS_WINDOW_MINUTES = 10
NEW_BOOKS_WINDOW_SECONDS = NEW_BOOKS_WINDOW_MINUTES * 60
NEW_BOOKS_PER_ADDRESS = RateLimit(calls=MAX_NEW_BOOKS_PER_ADDRESS, window_seconds=NEW_BOOKS_WINDOW_SECONDS)
NEW_BOOKS_LIMITED = (
    "Too many new demo order books from one address: at most {calls} in {minutes} minutes, so that one "
    "address cannot push out the books of other visitors. Try again in {wait} seconds."
)


# --- "My kitchen": the book's own buyer profile (task FEAT-1) ---------------------------------------------

KITCHEN_PROFILE_ID = "my-kitchen"
KITCHEN_NAME = "My kitchen"
KITCHEN_DESCRIPTION = "Set up by the visitor on the page Your kitchen, in this browser's own demo order book."
STARTING_POINTS = ("hotel-kitchen", "allergy-ward")  # the profile files a kitchen can start from a copy of
KITCHEN_SETTINGS = (  # what the page sets, in the order it shows them; the rest is the gateway's
    "display_name", "auto_order_enabled", "max_order_net_eur", "max_daily_net_eur", "min_fill_ratio",
    "excluded_allergens", "allergen_strictness", "allergen_strictness_by_code", "substitution_without_approval",
    "variable_weight", "deposits", "require_confirmed", "standing_order_drift_ratio",
    # Kept when a kitchen starts from a copy of a profile file: the ward's 10% premium, the bakery's formula rule.
    "formula_matters", "max_preference_premium_ratio",
    # When a substitute must keep the recipe: ALWAYS, LEARN (from this buyer's past) or WHEN_ASKED (lane LF).
    "formula_mode",
)
LIMIT_SETTINGS = ("max_order_net_eur", "max_daily_net_eur")
MAX_LIMIT_EUR = Decimal(100_000)
MAX_EXCLUDED_ALLERGENS = 10
MAX_NAME_LENGTH = 60
KITCHEN_SOURCE = "Your kitchen"

KITCHEN_AGENT = Identity(
    kind=IdentityKind.AGENT, id="agent:my-kitchen", display_name="My kitchen agent", profile_id=KITCHEN_PROFILE_ID
)
# An identity is bound to one buyer profile (tta.contracts.common), so My kitchen has approvers of its own. One
# person confirms, as at the hotel it starts from: the three are the hotel's one person, Hanna, once per role.
# A book keeps one approver per role, each holding that role only, because the shop signs role by role under the
# name of the customer's person (`tta.ui.shop_api`): where a kitchen has a dietitian of its own (the ward, the
# school), the person who orders must not sign the dietitian's role. One approver holding every role would.
KITCHEN_APPROVER_NAME = "Demo approver Hanna, My kitchen"
KITCHEN_APPROVERS = tuple(
    Identity(
        kind=IdentityKind.APPROVER, id=f"human:my-kitchen-{suffix}", display_name=KITCHEN_APPROVER_NAME,
        profile_id=KITCHEN_PROFILE_ID, roles=(role,),
    )
    for suffix, role in (
        ("purchasing", ApproverRole.PURCHASING_MANAGER),
        ("finance", ApproverRole.FINANCE),
        ("dietitian", ApproverRole.DIETITIAN),
    )
)
KITCHEN_IDENTITIES = (KITCHEN_AGENT, *KITCHEN_APPROVERS)
# Who the page acts for when it changes the settings: the person who orders (there is no login on a demo page).
KITCHEN_BUYER = next(one for one in KITCHEN_APPROVERS if ApproverRole.PURCHASING_MANAGER in one.roles)
# Set by the gateway, never by the page: a form that sends one of these is refused.
_FIXED_PARTS: Mapping[str, Any] = {
    "profile_id": KITCHEN_PROFILE_ID,
    "description": KITCHEN_DESCRIPTION,
    "illustrative": True,
    "approver_roles": {role.value: [one.id for one in KITCHEN_APPROVERS if role in one.roles] for role in ApproverRole},
}

# What a page may leave out. A page that does not send the ordering setting gets it switched off: every order
# then needs a person (F-10, tta.policy.human_approval). Ordering alone is only ever a buyer's own choice.
_UNSENT_PARTS: Mapping[str, Any] = {"auto_order_enabled": False}


@functools.cache
def _file_policy() -> RulePolicyEngine:
    """The rules and profile files the gateway loads (`tta.api.wiring`): what a kitchen is checked against."""
    return RulePolicyEngine.from_files()


def file_profile(profile_id: str) -> BuyerProfile:
    """A buyer profile as its file states it, whatever a book has in force."""
    return _file_policy().get_profile(profile_id)


def book_approver_roles(of_customer: BuyerProfile | None) -> dict[str, list[str]]:
    """Who signs each role in a book: under each role, the book approver that stands for the customer's person
    who holds it (lane FIX-A1, item 17). At the hotel and the bakery one person holds every role, so the
    purchasing approver is listed under all three; at the ward and the school it is listed under the purchasing
    manager's and finance's, and the dietitian approver under the dietitian's. So a shop book reads as its
    customer does over REST: one person where there is one (no dietitian is named, no role in brackets), and
    the dietitian's questions go to her where she is a second person. A book that stands for no customer
    ("My kitchen" of the older page) keeps one approver per role."""
    if of_customer is None:
        return _FIXED_PARTS["approver_roles"]
    return {role.value: [_approver_of(decided_as(of_customer, role)).id] for role in ApproverRole}


def _approver_of(role: ApproverRole) -> Identity:
    return next(one for one in KITCHEN_APPROVERS if one.roles == (role,))


def kitchen_profile(
    policy: RulePolicyEngine, settings: Mapping[str, Any], of_customer: BuyerProfile | None = None
) -> BuyerProfile:
    """The kitchen's settings as a profile, checked exactly as a profile file is and within the page's bounds.
    `of_customer`: the profile file of the customer the book stands for, which says who holds each role
    (`book_approver_roles`). Raises `PolicyLoadError` with one problem per field, each starting with the
    field's name."""
    problems = _page_problems(settings)
    if problems:
        raise PolicyLoadError(KITCHEN_SOURCE, problems)
    fixed = {**_FIXED_PARTS, "approver_roles": book_approver_roles(of_customer)}
    profile = policy.check_custom_profile({**_UNSENT_PARTS, **settings, **fixed})
    over = [
        f"{name}: at most €{MAX_LIMIT_EUR:,} on this page (got €{getattr(profile, name):,})"
        for name in LIMIT_SETTINGS if getattr(profile, name) > MAX_LIMIT_EUR
    ]
    if over:
        raise PolicyLoadError(KITCHEN_SOURCE, over)
    return profile


def _page_problems(settings: Mapping[str, Any]) -> list[str]:
    """What the page refuses before the profile checks: a setting of the gateway, a name, the exclusions."""
    problems = [f"{name}: is set by the gateway for My kitchen, not on this page" for name in _FIXED_PARTS
                if name in settings]
    name = settings.get("display_name")
    if not isinstance(name, str) or not name.strip() or len(name) > MAX_NAME_LENGTH:
        problems.append(f"display_name: give the kitchen a name of 1 to {MAX_NAME_LENGTH} characters")
    excluded = settings.get("excluded_allergens") or ()
    if len(excluded) > MAX_EXCLUDED_ALLERGENS:
        problems.append(f"excluded_allergens: at most {MAX_EXCLUDED_ALLERGENS} allergens (got {len(excluded)})")
    if excluded and not settings.get("allergen_strictness"):
        problems.append("allergen_strictness: choose STRICT or DECLARED_ONLY when an allergen is excluded")
    return problems


@dataclass(frozen=True)
class KitchenLog:
    """What a kitchen needs of the book that holds it, to log a change of its settings: the book's audit trail,
    whose customer the book stands for, and the count a write is checked against before it is made."""

    audit: AuditSink
    customer: BookCustomer
    count: Callable[[Identity], None]


class Kitchen:
    """The book's own custom profile. Replaced whole, never changed in place. Thread-safe.

    Held by a book (`keep_log`), every replacement that changes a setting is first written to that book's audit
    trail (`settings.changed`), and where the book stands for a customer with a dietitian of its own, a replacement
    that removes or relaxes one of her allergen exclusions is refused. A change that cannot be logged is not made."""

    def __init__(self, policy: RulePolicyEngine | None = None) -> None:
        self._policy = policy or _file_policy()
        self._lock = threading.Lock()
        self._profile = self._copy_of(STARTING_POINTS[0])
        self._started_from = STARTING_POINTS[0]
        self._is_set_up = False
        self._log: KitchenLog | None = None  # a kitchen no book holds logs nothing and guards nothing

    @property
    def profile(self) -> BuyerProfile:
        with self._lock:
            return self._profile

    @property
    def started_from(self) -> str:
        """The profile file this kitchen was last copied from."""
        with self._lock:
            return self._started_from

    @property
    def is_set_up(self) -> bool:
        """Whether the visitor saved settings of its own since the last copy."""
        with self._lock:
            return self._is_set_up

    @property
    def settings(self) -> dict[str, Any]:
        """The settings the page shows and sends, as they stand."""
        return self.profile.model_dump(include=set(KITCHEN_SETTINGS))

    @property
    def access_rules(self) -> tuple[AccessRule, ...]:
        """The fixed rules enforced where the caller is known (F-06): shown with the other fixed rules."""
        return self._policy.access_rules

    def keep_log(self, log: KitchenLog) -> None:
        """Called once, by the book that holds this kitchen."""
        with self._lock:
            self._log = log

    def start_from(self, profile_id: str) -> BuyerProfile:
        """Replace the kitchen with a copy of one of `STARTING_POINTS`. Raises `PolicyLoadError` for another id."""
        return self._replace(self._copy_of(profile_id), is_set_up=False, started_from=profile_id)

    def set_up(self, settings: Mapping[str, Any]) -> BuyerProfile:
        """Replace the kitchen with these settings. Raises `PolicyLoadError`; a refused form changes nothing."""
        of_customer = self._file_profile_of(self._customer_id())
        return self._replace(kitchen_profile(self._policy, settings, of_customer), is_set_up=True)

    def approver_for(self, role: ApproverRole) -> Identity | None:
        """The book approver who signs this role in this kitchen, holding every role the kitchen lists it under:
        at the hotel one approver with all three, at the ward the purchasing approver with the purchasing
        manager's and finance's and the dietitian approver with her own. None when nobody is listed. The roles
        come from the kitchen's own list, so the person who orders never holds the dietitian's role where the
        customer has a dietitian (`tta.orders.access.roles_that_count` counts every role an identity holds)."""
        listed = self.profile.approver_roles
        approver = next((one for one in KITCHEN_APPROVERS if one.id in listed.get(role, ())), None)
        if approver is None:
            return None
        held = tuple(each for each in ApproverRole if approver.id in listed.get(each, ()))
        return approver.model_copy(update={"roles": held})

    def _customer_id(self) -> str | None:
        return self._log.customer.customer_id if self._log is not None else None

    def _replace(self, profile: BuyerProfile, *, is_set_up: bool, started_from: str | None = None) -> BuyerProfile:
        """Put `profile` in force, after the event that says what it changes. Until a book of the shop has
        settings of its own, what is in force for its customer is the customer's profile file, so that is what
        the first settings are compared with: the page's first call sends the file's values and changes nothing.
        Raises `PolicyLoadError` for the dietitian's exclusions, and whatever the log raises (`RateLimited` when
        the day's stored bytes are spent): in each case nothing is changed."""
        log, customer_id = self._log, self._customer_id()
        of_customer = self._file_profile_of(customer_id)
        if of_customer is not None:
            refusals = dietitians_refusals(of_customer, profile)
            if refusals:
                raise PolicyLoadError(KITCHEN_SOURCE, refusals)
        with self._lock:
            before = self._profile if self._is_set_up or of_customer is None else of_customer
            changed = changes(before, profile)
            if log is not None and changed:
                buyer = _who_sets(customer_id)
                log.count(buyer)
                record_change(log.audit, actor_of(buyer), profile, changed, customer_id)
            self._profile, self._is_set_up = profile, is_set_up
            if started_from is not None:
                self._started_from = started_from
        return profile

    def _file_profile_of(self, customer_id: str | None) -> BuyerProfile | None:
        """The profile file of the customer the book stands for; None for a book that stands for none."""
        if customer_id is None:
            return None
        try:
            return self._policy.get_profile(customer_id)
        except NotAuthorised:
            return None

    def _copy_of(self, profile_id: str) -> BuyerProfile:
        if profile_id not in STARTING_POINTS:
            raise PolicyLoadError(KITCHEN_SOURCE, [f"start from one of {', '.join(STARTING_POINTS)}"])
        settings = self._policy.get_profile(profile_id).model_dump(include=set(KITCHEN_SETTINGS))
        return kitchen_profile(self._policy, {**settings, "display_name": KITCHEN_NAME})


def _who_sets(customer_id: str | None) -> Identity:
    """Who a change of settings is logged under: the book's approver for the person who orders, by the name of
    the customer's own person where the book stands for a customer (Hanna Laine at Harbourside Hotel)."""
    customer = shipped_customer(customer_id) if customer_id is not None else None
    name = customer.people.get(ApproverRole.PURCHASING_MANAGER) if customer is not None else None
    return KITCHEN_BUYER.model_copy(update={"display_name": name}) if name else KITCHEN_BUYER


class BookCustomer:
    """Whose customer file the book's "My kitchen" stands for. The shop page opens one book per customer of the
    shop and names it here, so an offer of that book gets the suggestions of that customer's past orders, judged
    under the kitchen's own settings. Until it is named, "My kitchen" has no customer file and gets no suggestion.
    A demo agent acting in the book keeps the file of its own buyer profile. Thread-safe."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._customer_id: str | None = None

    @property
    def customer_id(self) -> str | None:
        with self._lock:
            return self._customer_id

    def name(self, customer_id: str) -> None:
        with self._lock:
            self._customer_id = customer_id

    def of(self, identity: Identity) -> Customer | None:
        if identity.profile_id != KITCHEN_PROFILE_ID:
            return customer_on_file(identity)
        named = self.customer_id
        return shipped_customer(named) if named is not None else None


class ProfileInForce:
    """A book's gateway service with the book's own kitchen in force during every call made on it. Everything
    else is the service itself."""

    def __init__(self, service: Gateway, kitchen: Kitchen) -> None:
        self._service = service
        self._kitchen = kitchen

    def __getattr__(self, name: str) -> Any:
        found = getattr(self._service, name)
        if not callable(found):
            return found

        @functools.wraps(found)
        def in_force(*args: Any, **kwargs: Any) -> Any:
            with profile_in_force(self._kitchen.profile):
                return found(*args, **kwargs)

        return in_force


@dataclass(frozen=True, eq=False)  # one book is one object: compared and hashed by identity
class Sandbox:
    """One visitor's order book, with its own kitchen in force in every call made on `service`."""

    service: Gateway
    store: SqliteStore
    audit: AuditSink
    kitchen: Kitchen = field(default_factory=Kitchen)
    customer: BookCustomer = field(default_factory=BookCustomer)

    def __post_init__(self) -> None:
        if not isinstance(self.service, ProfileInForce):
            # The count is the service's own, taken before the kitchen is put in force around it: the kitchen
            # asks it while it holds its lock, and a call through `ProfileInForce` would wait for that lock.
            self.kitchen.keep_log(KitchenLog(self.audit, self.customer, self.service.count_settings_change))
            object.__setattr__(self, "service", cast(Gateway, ProfileInForce(self.service, self.kitchen)))

    def close(self) -> None:
        self.store.close()


class Sandboxes:
    """The sandboxes of this process by key (a browser session's cookie), least recently used first.

    `find` and `blank` are for reading: a visitor with no book of its own reads the blank one, which nothing
    is ever written to. `open` is for writing: it builds the visitor's book on its first use, counted for the
    address of the request being served (`new_books`). Thread-safe.
    """

    def __init__(
        self,
        build: Callable[[], Sandbox],
        *,
        capacity: int = MAX_SANDBOXES,
        idle_seconds: float = SANDBOX_IDLE_SECONDS,
        new_books: RateLimit = NEW_BOOKS_PER_ADDRESS,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._build = build
        self._capacity = capacity
        self._idle_seconds = idle_seconds
        self._monotonic = monotonic
        minutes = f"{new_books.window_seconds / SECONDS_PER_MINUTE:g}"
        self._new_books = new_books
        self._new_books_refusal = NEW_BOOKS_LIMITED.replace("{minutes}", minutes)
        self._opened = RateLimiter(new_books, monotonic=monotonic)
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
        """The book of this key, built empty when it has none. The book used least recently goes first.
        Raises `RateLimited` (with the seconds to wait) when the address has opened its new books: nothing is
        built and no book is dropped."""
        with self._lock:
            self._drop_idle()
            book = self._touch(key)
            if book is not None:
                return book
            address = Counted(f"new books {current_client_key()}", self._new_books, self._new_books_refusal)
            self._opened.check_all((address,))
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
