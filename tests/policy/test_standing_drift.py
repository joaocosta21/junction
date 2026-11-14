"""Rule P-08: a renewal of a standing order whose quantity or unit price drifts from its history goes to a human.

Valio Aimo's scenario: the agent "flags anomalies (portion counts creeping up, cost drifting) before auto-renewing".
AIMO/USE-CASES.md section 6 measured the gap: seven orders of 469363 growing from 100 to 290 L were all AUTO.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tta.contracts.common import ApproverRole, Unit, Verdict
from tta.contracts.offer import Coverage, OfferLine, OfferOption
from tta.contracts.policy import BuyerProfile, PolicyContext
from tta.contracts.standing import DriftKind, Renewal, RenewalLine, StandingHistory
from tta.policy import RulePolicyEngine
from tta.policy.drift import DRIFT_WINDOW, MIN_RENEWALS_TO_JUDGE, assess_drift
from tta.policy.facts import OrderScope, read_fact

NOW = datetime(2026, 11, 14, 2, 52, tzinfo=timezone(timedelta(hours=2)))
PRODUCT = "469363"
PRICE = "2.48"
USUAL = (100, 96, 104, 100, 98, 102)  # the demo's six synthetic weeks: median 100 L


def _renewal(index: int, litres: int | str, price: str = PRICE, *, synthetic: bool = True) -> Renewal:
    line = RenewalLine(
        request_line_index=0, product_id=PRODUCT, quantity=Decimal(litres), unit=Unit.L,
        unit_net_price_eur=Decimal(price),
    )
    return Renewal(
        renewal_id=f"ren_{index}", standing_order_id="so_milk", renewed_at=NOW - timedelta(weeks=10 - index),
        lines=(line,), synthetic=synthetic, order_id=None if synthetic else f"ord_{index}",
    )


def _history(quantities: Sequence[int | str] = USUAL, prices: Sequence[str] | None = None) -> StandingHistory:
    paid = prices or [PRICE] * len(quantities)
    pairs = enumerate(zip(quantities, paid, strict=True))
    renewals = tuple(_renewal(index, litres, price) for index, (litres, price) in pairs)
    return StandingHistory(standing_order_id="so_milk", name="Weekly lactose-free milk, hotel kitchen",
                           renewals=renewals)


@pytest.fixture
def renewal_option(
    make_line: Callable[..., OfferLine], make_option: Callable[..., OfferOption]
) -> Callable[..., OfferOption]:
    def build(litres: int = 100, price: str = PRICE) -> OfferOption:
        line = make_line(PRODUCT, "Lactose free milk 1 l", quantity=str(litres), unit_net_price=price)
        option = make_option([line], net=str(line.net), needed_by=None)
        coverage = Coverage(request_line_index=0, requested=Decimal(litres), covered=Decimal(litres), unit=Unit.L,
                            fill_ratio=Decimal(1), missing=Decimal(0))
        return option.model_copy(update={"coverage": (coverage,)})

    return build


def _context(history: StandingHistory | None) -> PolicyContext:
    return PolicyContext(now=NOW, day_committed_net_eur=Decimal(0), standing_history=history)


def _p08(decision) -> list:
    return [rule for rule in decision.fired if rule.rule_id == "P-08"]


def test_a_renewal_at_the_usual_quantity_is_ordered_alone(
    engine: RulePolicyEngine, hotel: BuyerProfile, renewal_option: Callable[..., OfferOption]
) -> None:
    decision = engine.evaluate(renewal_option(100), hotel, _context(_history()))

    assert decision.verdict is Verdict.AUTO and decision.fired == ()


def test_290_litres_against_a_median_of_100_goes_to_the_purchasing_manager(
    engine: RulePolicyEngine, hotel: BuyerProfile, renewal_option: Callable[..., OfferOption]
) -> None:
    decision = engine.evaluate(renewal_option(290), hotel, _context(_history()))

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("P-08",)
    assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)
    rule = _p08(decision)[0]
    assert rule.sentence == (
        "For standing order so_milk, 290 L this week against a median of 100 L over the last 6 renewals, more "
        "than the 25% tolerance of profile hotel-kitchen."
    )
    assert rule.fixed is False and rule.product_id is None
    assert rule.facts["standing.largest_drift"] == 1.9
    assert rule.facts["standing.renewals_compared"] == 6
    assert rule.facts["standing.standing_order_id"] == "so_milk"
    assert rule.facts["profile.standing_order_drift_ratio"] == 0.25


def test_a_unit_price_that_drifts_goes_to_a_human_with_both_prices(
    engine: RulePolicyEngine, hotel: BuyerProfile, renewal_option: Callable[..., OfferOption]
) -> None:
    decision = engine.evaluate(renewal_option(100, price="3.20"), hotel, _context(_history()))

    assert decision.rule_ids == ("P-08",)
    assert "€3.20 per ST of 469363 this week against a median of €2.48 over the last 6 renewals" in (
        _p08(decision)[0].sentence
    )


def test_a_drift_within_the_tolerance_does_not_fire(
    engine: RulePolicyEngine, hotel: BuyerProfile, renewal_option: Callable[..., OfferOption]
) -> None:
    decision = engine.evaluate(renewal_option(125), hotel, _context(_history()))  # exactly 25%: not more

    assert decision.verdict is Verdict.AUTO


def test_a_request_that_renews_nothing_never_fires_p08_nor_a_missing_fact(
    engine: RulePolicyEngine, hotel: BuyerProfile, renewal_option: Callable[..., OfferOption]
) -> None:
    no_tolerance = hotel.model_copy(update={"standing_order_drift_ratio": None})

    for profile in (hotel, no_tolerance):
        decision = engine.evaluate(renewal_option(290), profile, _context(None))
        assert decision.verdict is Verdict.AUTO and decision.fired == ()


def test_a_history_too_short_to_judge_does_not_fire_and_the_report_says_so(
    engine: RulePolicyEngine, hotel: BuyerProfile, renewal_option: Callable[..., OfferOption]
) -> None:
    short = _history(USUAL[: MIN_RENEWALS_TO_JUDGE - 1])
    option = renewal_option(290)

    decision = engine.evaluate(option, hotel, _context(short))
    report = assess_drift(option, short, hotel.standing_order_drift_ratio)

    assert decision.verdict is Verdict.AUTO
    assert report.judged is False and report.checks == ()
    assert report.sentence == (
        "Standing order so_milk has too short a history to judge drift: 2 past renewals on record, at least 3 are "
        "needed for a line. Rule P-08 does not apply to this renewal."
    )


def test_a_profile_without_a_tolerance_sends_a_judged_renewal_to_a_human_for_the_missing_fact(
    engine: RulePolicyEngine, hotel: BuyerProfile, renewal_option: Callable[..., OfferOption]
) -> None:
    no_tolerance = hotel.model_copy(update={"standing_order_drift_ratio": None})

    decision = engine.evaluate(renewal_option(100), no_tolerance, _context(_history()))

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-03",)
    assert decision.fired[0].facts["missing_fact"] == "profile.standing_order_drift_ratio"
    assert decision.fired[0].facts["needed_by"] == ["P-08"]


def test_the_median_is_taken_over_the_last_window_of_renewals(renewal_option: Callable[..., OfferOption]) -> None:
    # Ten weeks: the first four at 300 L fall outside the window of six, whose median is 100 L.
    history = _history((300, 300, 300, 300, *USUAL))

    report = assess_drift(renewal_option(100), history, Decimal("0.25"))

    quantity = next(check for check in report.checks if check.kind is DriftKind.QUANTITY)
    assert (quantity.median, quantity.renewals, quantity.over_tolerance) == (Decimal(100), DRIFT_WINDOW, False)
    assert report.synthetic_renewals == DRIFT_WINDOW
    assert report.sentence.startswith("Standing order so_milk is within the 25% tolerance: 100 L this week")
    assert report.sentence.endswith(
        "6 renewals of the history are synthetic, made up for the demonstration: the Valio Aimo mock has no order "
        "history."
    )


def test_a_product_new_to_the_history_has_its_price_left_uncompared(
    make_line: Callable[..., OfferLine], renewal_option: Callable[..., OfferOption]
) -> None:
    option = renewal_option(100)
    other = make_line("462775", "Lactose free milk 1,5 l", quantity="10", unit_net_price="2.57")
    option = option.model_copy(update={"lines": (*option.lines, other)})

    report = assess_drift(option, _history(), Decimal("0.25"))

    assert {check.kind for check in report.checks} == {DriftKind.QUANTITY, DriftKind.UNIT_PRICE}
    assert report.not_compared == ("the unit price of 462775 (0 past renewals, at least 3 needed)",)


def test_the_engine_has_a_reader_for_every_standing_fact(
    hotel: BuyerProfile, renewal_option: Callable[..., OfferOption]
) -> None:
    scope = OrderScope(renewal_option(290), hotel, _context(_history()), {})

    assert read_fact("standing.is_renewal", scope) is True
    assert read_fact("standing.history_judged", scope) is True
    assert read_fact("standing.largest_drift", scope) == Decimal("1.9")
    assert read_fact("standing.drift_found", scope).startswith("for standing order so_milk, 290 L")


def test_the_authority_texts_state_the_window_and_minimum_of_the_code(
    engine: RulePolicyEngine, hotel: BuyerProfile
) -> None:
    rules = {rule.rule_id: rule for rule in engine.describe_authority(hotel).rules}
    unset = engine.describe_authority(hotel.model_copy(update={"standing_order_drift_ratio": None}))

    sentence = rules["P-08"].sentence
    assert "more than 25%" in sentence and f"last {DRIFT_WINDOW} renewals" in sentence
    assert f"fewer than {MIN_RENEWALS_TO_JUDGE} past renewals" in sentence
    assert rules["P-08"].approver_role is ApproverRole.PURCHASING_MANAGER and rules["P-08"].fixed is False
    assert "sets no drift tolerance" in next(rule.sentence for rule in unset.rules if rule.rule_id == "P-08")
