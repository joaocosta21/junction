"""A buyer profile that is not a file: set up by a visitor of the pages ("My kitchen", task FEAT-1).

Scores on the 20% "autonomy and controls": a buyer sets what its agent may decide alone. Such a profile is
checked exactly as a profile file is (`RulePolicyEngine.check_custom_profile`), and it is in force only inside
the call that carries it: `profile_in_force` makes every engine of the process find it by its id for the
duration of one `with` block, in this thread of control only. It never shadows a profile file, it is never
listed by `profile_ids`, and outside the block its id is unknown, as any other id nobody set up.

A context variable rather than an argument: the services ask the engine for a profile by the id of the caller's
identity, and the request parser holds an engine of its own. Every one of them must find the same profile, and
none of them may find another visitor's.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from tta.contracts.policy import BuyerProfile

_IN_FORCE: ContextVar[BuyerProfile | None] = ContextVar("tta_profile_in_force", default=None)


@contextmanager
def profile_in_force(profile: BuyerProfile) -> Iterator[None]:
    """Inside the block, every engine finds `profile` by its id, unless a profile file has that id."""
    token = _IN_FORCE.set(profile)
    try:
        yield
    finally:
        _IN_FORCE.reset(token)


def custom_profile(profile_id: str) -> BuyerProfile | None:
    """The profile in force when it has this id; otherwise `None`."""
    profile = _IN_FORCE.get()
    return profile if profile is not None and profile.profile_id == profile_id else None
