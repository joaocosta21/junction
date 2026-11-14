"""The claims that gate an order (SPEC section 4, "Which claims gate"): F-01, F-07, and F-03 for a missing claim.

Price and quantity always gate; the delivery date gates when the request gave a needed-by date, through the
option's needed-by check; origin never does. A claim the line does not carry is a missing fact, never a pass.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from tta.contracts.availability import ClaimCheck
from tta.contracts.common import (
    AllergenRelation,
    AllergenStrictness,
    ApproverRole,
    AvailabilityState,
    CheckResult,
    ClaimName,
    ClaimStatus,
    ConstraintKind,
    Verdict,
)
from tta.contracts.offer import ConstraintCheck, OfferLine, OfferOption
from tta.contracts.policy import BuyerProfile, FiredRule, PolicyContext, PolicyDecision
from tta.policy import RulePolicyEngine

NOT_CONFIRMED = [ClaimStatus.UNKNOWN, ClaimStatus.RULED_OUT]
NOT_MET = [CheckResult.NOT_MET, CheckResult.UNVERIFIED]
MILK = "Arla Café milk 1 L UHT (463380)"


def _fired(decision: PolicyDecision, rule_id: str) -> list[FiredRule]:
    return [rule for rule in decision.fired if rule.rule_id == rule_id]


def _with_claim(line: OfferLine, claim: ClaimName, status: ClaimStatus) -> OfferLine:
    """The line with one more statement about a claim it already carries."""
    extra = ClaimCheck(claim=claim, status=status, sentence="A second statement.")
    return line.model_copy(update={"claims": (*line.claims, extra)})


# --- a claim the line does not carry is a missing fact (F-03) -------------------------------------------------

def test_the_test_line_carries_all_five_claims_and_the_test_option_a_needed_by_check(
    make_line: Callable[..., OfferLine], make_option: Callable[..., OfferOption],
) -> None:
    option = make_option()

    assert [check.claim for check in make_line().claims] == list(ClaimName)
    assert [check.kind for check in option.constraint_checks] == [ConstraintKind.NEEDED_BY]
    assert make_option(needed_by=None).constraint_checks == ()


def test_a_confirmed_line_without_a_quantity_claim_goes_to_the_purchasing_manager_by_f03(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    option = make_option((make_line(quantity_claim=None),))

    decision = engine.evaluate(option, hotel, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-03",)
    assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)
    f03 = decision.fired[0]
    assert f03.product_id == "463380"
    assert f03.facts == {
        "missing_fact": "line.quantity_confirmed",
        "reason": "the offer line carries no quantity claim",
        "needed_by": ["F-01"],
    }
    assert f03.sentence == (
        f"The quantity confirmation of {MILK} is missing (the offer line carries no quantity claim), so rule "
        "F-01 cannot be checked."
    )


def test_a_line_without_a_price_claim_goes_to_the_purchasing_manager_by_f03(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    option = make_option((make_line(price_claim=None),))

    decision = engine.evaluate(option, hotel, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-03",)
    assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)
    f03 = decision.fired[0]
    assert f03.product_id == "463380"
    assert f03.facts["missing_fact"] == "line.price_claim" and f03.facts["needed_by"] == ["F-07"]
    assert f03.sentence == (
        f"The price claim of {MILK} is missing (the offer line carries no price claim), so rule F-07 cannot "
        "be checked."
    )


@pytest.mark.parametrize("needed_by", [CheckResult.MET, None], ids=["dated request", "request without a date"])
def test_a_line_without_a_delivery_date_claim_goes_to_the_purchasing_manager_by_f03(
    needed_by: CheckResult | None, engine: RulePolicyEngine, hotel: BuyerProfile,
    make_line: Callable[..., OfferLine], make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    option = make_option((make_line(delivery_date_claim=None),), needed_by=needed_by)

    decision = engine.evaluate(option, hotel, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-03",)
    assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)
    assert decision.fired[0].facts == {
        "missing_fact": "line.delivery_date_claim",
        "reason": "the offer line carries no delivery-date claim",
        "needed_by": ["F-07"],
    }


def test_a_line_without_any_claim_is_never_ordered_alone_and_every_gap_is_listed(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    bare = make_line(
        price_claim=None, quantity_claim=None, delivery_date_claim=None, allergens_claim=None, origin_claim=None
    )

    decision = engine.evaluate(make_option((bare,)), hotel, make_context())

    assert bare.claims == ()
    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-03", "F-03", "F-03")
    assert [rule.facts["missing_fact"] for rule in decision.fired] == [
        "line.quantity_confirmed", "line.price_claim", "line.delivery_date_claim",
    ]


def test_a_missing_quantity_claim_does_not_hide_a_state_that_already_says_not_confirmed(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    line = make_line(state=AvailabilityState.QUANTITY_NOT_CONFIRMED, quantity_claim=None)

    decision = engine.evaluate(make_option((line,)), hotel, make_context())

    assert decision.rule_ids == ("F-01",)  # the state settles it: no claim is needed to say "not confirmed"


def test_a_missing_price_claim_is_not_listed_when_the_delivery_date_already_fires_f07(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    line = make_line(price_claim=None, delivery_date_claim=ClaimStatus.RULED_OUT)

    decision = engine.evaluate(make_option((line,)), hotel, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-07",)
    assert decision.fired[0].facts["line.price_claim"] is None
    assert decision.fired[0].sentence == f"For {MILK} the delivery date is ruled out."


# --- F-07 on a line: the price is not confirmed, or the delivery date is ruled out ---------------------------

@pytest.mark.parametrize("status", NOT_CONFIRMED)
def test_f07_sends_a_line_whose_price_is_not_confirmed_to_the_purchasing_manager(
    status: ClaimStatus, engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    option = make_option((make_line(price_claim=status),))

    decision = engine.evaluate(option, hotel, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-07",)
    assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)
    f07 = decision.fired[0]
    assert f07.fixed and f07.verdict is Verdict.APPROVAL and f07.product_id == "463380"
    assert f07.approver_role is ApproverRole.PURCHASING_MANAGER
    assert f07.sentence == f"For {MILK} the price is not confirmed by Valio Aimo."
    assert f07.facts == {
        "line.price_claim": status.value,
        "line.delivery_date_claim": "CONFIRMED",
        "line.name": "Arla Café milk 1 L UHT",
        "line.product_id": "463380",
        "line.unconfirmed_reason": "the price is not confirmed by Valio Aimo",
    }
    assert decision.sentence == (
        f"The agent cannot place this order alone: for {MILK} the price is not confirmed by Valio Aimo (F-07). "
        "It needs the purchasing manager."
    )


@pytest.mark.parametrize("needed_by", [CheckResult.MET, None], ids=["dated request", "request without a date"])
def test_f07_sends_a_line_whose_delivery_date_is_ruled_out_to_the_purchasing_manager(
    needed_by: CheckResult | None, engine: RulePolicyEngine, hotel: BuyerProfile,
    make_line: Callable[..., OfferLine], make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    option = make_option((make_line(delivery_date_claim=ClaimStatus.RULED_OUT),), needed_by=needed_by)

    decision = engine.evaluate(option, hotel, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-07",)
    assert decision.fired[0].product_id == "463380"
    assert decision.fired[0].sentence == f"For {MILK} the delivery date is ruled out."
    assert decision.fired[0].facts["line.delivery_date_claim"] == "RULED_OUT"


def test_f07_fires_once_per_line_and_gives_both_reasons(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    lines = (
        make_line("463380"),
        make_line("462775", "Milk drink", price_claim=ClaimStatus.UNKNOWN, delivery_date_claim=ClaimStatus.RULED_OUT),
        make_line("469363", "Other milk", price_claim=ClaimStatus.UNKNOWN),
    )

    decision = engine.evaluate(make_option(lines), hotel, make_context())

    assert [(rule.rule_id, rule.product_id) for rule in decision.fired] == [("F-07", "462775"), ("F-07", "469363")]
    assert decision.fired[0].sentence == (
        "For Milk drink (462775) the price is not confirmed by Valio Aimo and the delivery date is ruled out."
    )


def test_f07_is_listed_after_f01_when_neither_quantity_nor_price_is_confirmed(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    line = make_line(
        state=AvailabilityState.QUANTITY_NOT_CONFIRMED, quantity_claim=ClaimStatus.UNKNOWN,
        price_claim=ClaimStatus.UNKNOWN,
    )

    decision = engine.evaluate(make_option((line,)), hotel, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-01", "F-07")


@pytest.mark.parametrize(
    ("claim", "rule_id"), [(ClaimName.QUANTITY, "F-01"), (ClaimName.PRICE, "F-07")], ids=["quantity", "price"]
)
def test_a_claim_stated_twice_counts_as_its_least_favourable_statement(
    claim: ClaimName, rule_id: str, engine: RulePolicyEngine, hotel: BuyerProfile,
    make_line: Callable[..., OfferLine], make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    line = _with_claim(make_line(), claim, ClaimStatus.UNKNOWN)

    assert engine.evaluate(make_option((line,)), hotel, make_context()).rule_ids == (rule_id,)


def test_a_delivery_date_stated_twice_is_ruled_out_when_one_statement_says_so(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    line = _with_claim(make_line(), ClaimName.DELIVERY_DATE, ClaimStatus.RULED_OUT)

    decision = engine.evaluate(make_option((line,)), hotel, make_context())

    assert decision.rule_ids == ("F-07",) and decision.fired[0].facts["line.delivery_date_claim"] == "RULED_OUT"


# --- F-07 on the option: the needed-by date is not verifiably met --------------------------------------------

@pytest.mark.parametrize(
    ("result", "finding"),
    [(CheckResult.NOT_MET, "is not met"), (CheckResult.UNVERIFIED, "cannot be verified")],
)
def test_f07_sends_an_option_that_does_not_verifiably_meet_the_needed_by_date_to_the_purchasing_manager(
    result: CheckResult, finding: str, engine: RulePolicyEngine, hotel: BuyerProfile,
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(make_option(needed_by=result), hotel, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-07",)
    assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)
    f07 = decision.fired[0]
    assert f07.fixed and f07.product_id is None and f07.approver_role is ApproverRole.PURCHASING_MANAGER
    assert f07.sentence == f"The needed-by date 2026-11-16 {finding} for this option."
    assert f07.facts == {
        "option.needed_by_check": result.value,
        "option.needed_by": "2026-11-16",
        "option.needed_by_finding": finding,
    }


def test_f07_fires_on_the_option_and_on_the_line_that_misses_the_date(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    late = make_line("462775", "Milk drink", delivery_date_claim=ClaimStatus.RULED_OUT)
    option = make_option((make_line(), late), needed_by=CheckResult.NOT_MET)

    decision = engine.evaluate(option, hotel, make_context())

    assert [(rule.rule_id, rule.product_id) for rule in decision.fired] == [("F-07", "462775"), ("F-07", None)]
    assert all(rule.title == decision.fired[0].title for rule in decision.fired)
    assert decision.sentence == (
        "The agent cannot place this order alone: for Milk drink (462775) the delivery date is ruled out (F-07) "
        "and the needed-by date 2026-11-16 is not met for this option (F-07). It needs the purchasing manager."
    )


def test_the_least_favourable_needed_by_check_counts_when_an_option_carries_several(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    met = make_option().constraint_checks[0]
    checks = (
        met,
        ConstraintCheck(request_line_index=1, kind=ConstraintKind.NEEDED_BY, subject="2026-11-17",
                        result=CheckResult.UNVERIFIED, sentence="Not verified."),
        ConstraintCheck(request_line_index=2, kind=ConstraintKind.NEEDED_BY, subject="2026-11-18",
                        result=CheckResult.NOT_MET, sentence="Not met."),
        ConstraintCheck(kind=ConstraintKind.QUANTITY, subject="1000 L", result=CheckResult.NOT_MET,
                        sentence="A check of another kind is not this rule's business."),
    )
    option = make_option().model_copy(update={"constraint_checks": checks})

    decision = engine.evaluate(option, hotel, make_context())

    assert decision.rule_ids == ("F-07",)
    assert decision.fired[0].facts["option.needed_by_check"] == "NOT_MET"
    assert decision.fired[0].sentence == "The needed-by date 2026-11-18 is not met for this option."


# --- what does not send an order to a human -----------------------------------------------------------------

@pytest.mark.parametrize("status", [ClaimStatus.UNKNOWN, ClaimStatus.CONFIRMED])
def test_a_request_without_a_date_is_not_sent_to_a_human_for_that_reason_alone(
    status: ClaimStatus, engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    option = make_option((make_line(delivery_date_claim=status),), needed_by=None)

    decision = engine.evaluate(option, hotel, make_context())

    assert decision.verdict is Verdict.AUTO and decision.fired == ()


@pytest.mark.parametrize("status", [None, ClaimStatus.UNKNOWN], ids=["absent", "unknown"])
def test_the_origin_claim_never_gates_an_order(
    status: ClaimStatus | None, engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    option = make_option((make_line(origin_claim=status),))

    assert engine.evaluate(option, hotel, make_context()).verdict is Verdict.AUTO


def test_allergens_gate_through_the_allergen_rule_so_declared_only_still_passes_a_product_without_a_statement(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
    make_allergen_check: Callable,
) -> None:
    """SPEC section 6, DECLARED_ONLY: no statement passes and is shown as unverified. That buyer chose so."""
    check = make_allergen_check({"AP": AllergenRelation.NOT_STATED}, strictness=AllergenStrictness.DECLARED_ONLY)
    line = make_line(allergen_check=check, allergens_claim=ClaimStatus.UNKNOWN)

    assert engine.evaluate(make_option((line,)), hotel, make_context()).verdict is Verdict.AUTO
