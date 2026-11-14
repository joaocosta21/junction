"""F-04: at order time an option that expired or changed cannot be ordered (SPEC sections 7 and 8)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest

from tta.contracts.availability import RevalidationChange, RevalidationResult
from tta.contracts.common import DataSource, Verdict
from tta.contracts.offer import OfferOption
from tta.contracts.policy import BuyerProfile, FiredRule, PolicyContext, PolicyDecision
from tta.policy import RulePolicyEngine


def _fired(decision: PolicyDecision, rule_id: str) -> FiredRule:
    return next(rule for rule in decision.fired if rule.rule_id == rule_id)


def test_f04_is_silent_at_order_time_when_nothing_changed_and_nothing_expired(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext], make_revalidation: Callable,
) -> None:
    context = make_context(at_order_time=True, revalidation=make_revalidation())

    assert engine.evaluate(make_option(), hotel, context).verdict is Verdict.AUTO


@pytest.mark.parametrize(
    ("revalidation", "expected_expired"),
    [({"ok": False, "changed_price": True}, False), ({"ok": False, "expired": True}, True),
     ({"ok": True, "expired": True}, True), ({"ok": True, "changed_price": True}, False)],
    ids=["price changed", "expired", "expired but reported ok", "changed but reported ok"],
)
def test_f04_blocks_at_order_time_when_the_fresh_check_reports_a_change_or_an_expiry(
    revalidation: dict[str, bool], expected_expired: bool, engine: RulePolicyEngine, hotel: BuyerProfile,
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
    make_revalidation: Callable,
) -> None:
    context = make_context(at_order_time=True, revalidation=make_revalidation(**revalidation))

    decision = engine.evaluate(make_option(), hotel, context)

    assert decision.verdict is Verdict.BLOCK and decision.rule_ids == ("F-04",)
    f04 = _fired(decision, "F-04")
    assert f04.fixed and f04.facts["revalidation.ok"] is False
    assert f04.facts["revalidation.expired"] is expected_expired


def test_f04_blocks_at_order_time_when_the_option_is_past_its_valid_until(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext], make_revalidation: Callable, now,
) -> None:
    option = make_option(valid_until=now - timedelta(minutes=1))
    context = make_context(at_order_time=True, revalidation=make_revalidation())

    decision = engine.evaluate(option, hotel, context)

    assert decision.verdict is Verdict.BLOCK and decision.rule_ids == ("F-04",)
    assert _fired(decision, "F-04").sentence == (
        "This option can no longer be ordered as offered: it was valid until 2026-11-14 02:51+02:00."
    )


def test_f04_names_what_changed(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext], make_revalidation: Callable,
) -> None:
    context = make_context(at_order_time=True, revalidation=make_revalidation(ok=False, changed_price=True))

    decision = engine.evaluate(make_option(), hotel, context)

    assert _fired(decision, "F-04").sentence == (
        "This option can no longer be ordered as offered: the price of 463380 changed from 2.65 to 2.80."
    )


def test_f04_is_an_order_time_rule_and_stays_silent_while_the_offer_is_built(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext], make_revalidation: Callable, now,
) -> None:
    option = make_option(valid_until=now - timedelta(minutes=1))
    context = make_context(at_order_time=False, revalidation=make_revalidation(ok=False, expired=True))

    assert engine.evaluate(option, hotel, context).verdict is Verdict.AUTO


def test_f04_says_so_when_the_fresh_check_only_reports_an_expiry(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext], make_revalidation: Callable,
) -> None:
    context = make_context(at_order_time=True, revalidation=make_revalidation(ok=False, expired=True))

    decision = engine.evaluate(make_option(), hotel, context)

    assert _fired(decision, "F-04").sentence == (
        "This option can no longer be ordered as offered: a price validity or an order cut-off has passed."
    )
    assert decision.sentence == (
        "This order cannot be placed, even with approval: this option can no longer be ordered as offered: "
        "a price validity or an order cut-off has passed (F-04)."
    )


def test_f04_still_gives_a_reason_when_the_fresh_check_gives_none(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext], make_revalidation: Callable,
) -> None:
    context = make_context(at_order_time=True, revalidation=make_revalidation(ok=False))

    decision = engine.evaluate(make_option(), hotel, context)

    assert _fired(decision, "F-04").sentence == (
        "This option can no longer be ordered as offered: the fresh check of price and availability did not "
        "confirm it."
    )


def test_f04_names_every_change_and_keeps_the_facts_for_the_order_service(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext], now: datetime,
) -> None:
    changes = (
        RevalidationChange(product_id="463380", field="availability_state", before="CONFIRMED",
                           after="OUT_OF_STOCK", sentence="The stock of 463380 ran out."),
        RevalidationChange(product_id="462775", field="lot_size", before="1", after="6",
                           sentence="The lot size of 462775 changed."),
    )
    revalidation = RevalidationResult(ok=False, changes=changes, checked_at=now, source=DataSource.REPLAY)

    decision = engine.evaluate(make_option(), hotel, make_context(at_order_time=True, revalidation=revalidation))

    f04 = _fired(decision, "F-04")
    assert f04.sentence == (
        "This option can no longer be ordered as offered: the availability of 463380 changed from CONFIRMED to "
        "OUT_OF_STOCK and the lot size of 462775 changed from 1 to 6."
    )
    assert f04.facts["revalidation.changes"] == [
        "the availability of 463380 changed from CONFIRMED to OUT_OF_STOCK",
        "the lot size of 462775 changed from 1 to 6",
    ]
    assert f04.facts["option.valid_until"] == (now + timedelta(days=1)).isoformat()
    assert f04.facts["option.expired"] is False and f04.facts["context.at_order_time"] is True


def test_a_valid_until_without_an_offset_cannot_be_compared_and_goes_to_a_human(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext], make_revalidation: Callable, now: datetime,
) -> None:
    naive = (now + timedelta(days=1)).replace(tzinfo=None)
    context = make_context(at_order_time=True, revalidation=make_revalidation())

    decision = engine.evaluate(make_option(valid_until=naive), hotel, context)

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-03",)
    assert "one has no offset" in decision.fired[0].facts["reason"]


def test_the_clock_of_the_context_decides_not_the_wall_clock(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext], make_revalidation: Callable, now: datetime,
) -> None:
    option = make_option(valid_until=now + timedelta(hours=1))
    later = (now + timedelta(hours=2)).astimezone(UTC)

    before = engine.evaluate(option, hotel, make_context(at_order_time=True, revalidation=make_revalidation()))
    after = engine.evaluate(
        option, hotel, make_context(at_order_time=True, revalidation=make_revalidation(), at=later)
    )

    assert before.verdict is Verdict.AUTO and before.evaluated_at == now
    assert after.verdict is Verdict.BLOCK and after.evaluated_at == later


@pytest.mark.parametrize(
    ("seconds_left", "verdict"), [(0, Verdict.BLOCK), (1, Verdict.AUTO), (-1, Verdict.BLOCK)],
    ids=["at valid-until", "one second before", "one second after"],
)
def test_an_option_is_expired_from_the_moment_of_its_valid_until_as_a_cut_off_is(
    seconds_left: int, verdict: Verdict, engine: RulePolicyEngine, hotel: BuyerProfile,
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
    make_revalidation: Callable, now: datetime,
) -> None:
    """Availability treats a cut-off equal to the clock as passed (SPEC section 4); the option follows it."""
    option = make_option(valid_until=now + timedelta(seconds=seconds_left))
    context = make_context(at_order_time=True, revalidation=make_revalidation())

    decision = engine.evaluate(option, hotel, context)

    assert decision.verdict is verdict
    assert decision.rule_ids == (("F-04",) if verdict is Verdict.BLOCK else ())
