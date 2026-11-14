"""The facts of rule P-08: a request that renews a standing order, read against the order's history (task STAND-1).

A request that renews nothing carries no history (`PolicyContext.standing_history` is None). That is "not a
renewal", never a missing fact: every fact here then has a value, and P-08 is false on `standing.is_renewal`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import TYPE_CHECKING

from tta.contracts.standing import DriftReport
from tta.policy.drift import assess_drift, largest_drift, over_tolerance
from tta.policy.reading import Missing, Reading
from tta.policy.text import join_words

if TYPE_CHECKING:  # facts.py imports this module; OrderScope is only named in annotations
    from tta.policy.facts import OrderScope

NOT_A_RENEWAL = "the request renews no standing order"
NO_DRIFT = "no line of this renewal drifts beyond the profile's tolerance"


def drift_report(scope: OrderScope) -> DriftReport | None:
    """The drift of this option from the history it renews, under the profile's tolerance; None: not a renewal."""
    history = scope.context.standing_history
    if history is None:
        return None
    return assess_drift(scope.option, history, scope.profile.standing_order_drift_ratio)


def _is_renewal(scope: OrderScope) -> Reading:
    return scope.context.standing_history is not None


def _history_judged(scope: OrderScope) -> Reading:
    """False for a request that renews nothing, and for a renewal whose history is too short to judge."""
    report = drift_report(scope)
    return report is not None and report.judged


def _largest_drift(scope: OrderScope) -> Reading:
    report = drift_report(scope)
    return Decimal(0) if report is None else largest_drift(report)


def _drift_found(scope: OrderScope) -> Reading:
    """`for standing order so_1, 290 L this week against a median of 100 L over the last 6 renewals`."""
    report = drift_report(scope)
    over = over_tolerance(report) if report is not None else ()
    if report is None or not over:
        return Missing(NO_DRIFT if report is not None else NOT_A_RENEWAL)
    return f"for standing order {report.standing_order_id}, {join_words([check.sentence for check in over])}"


def _standing_order_id(scope: OrderScope) -> Reading:
    history = scope.context.standing_history
    return Missing(NOT_A_RENEWAL) if history is None else history.standing_order_id


def _renewals_compared(scope: OrderScope) -> Reading:
    """The most past renewals any comparison was taken over."""
    report = drift_report(scope)
    return Decimal(max((check.renewals for check in report.checks), default=0) if report is not None else 0)


STANDING_FACTS: Mapping[str, Callable[[OrderScope], Reading]] = {
    "standing.is_renewal": _is_renewal,
    "standing.history_judged": _history_judged,
    "standing.largest_drift": _largest_drift,
    "standing.drift_found": _drift_found,
    "standing.standing_order_id": _standing_order_id,
    "standing.renewals_compared": _renewals_compared,
}
