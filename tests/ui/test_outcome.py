"""The last line of a result: a headline and the gateway's sentence, for every way a request can end."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from tta.contracts.agent import AgentRun
from tta.contracts.common import OrderStatus, PlacedBy
from tta.ui.outcome import outcome_of_order, outcome_of_run
from tta.ui.run import Problem, ReadBy, RunRecord

OFFER = SimpleNamespace(options=("an option",))
EMPTY_OFFER = SimpleNamespace(options=())


def _order(status: OrderStatus, placed_by: PlacedBy | None = None, fired: tuple[str, ...] = ("P-01",)) -> Any:
    decision = SimpleNamespace(fired=tuple(SimpleNamespace(rule_id=rule_id) for rule_id in fired))
    sentence = "What the gateway says."
    return SimpleNamespace(status=status, placed_by=placed_by, decision=decision, status_sentence=sentence)


def _record(**fields: Any) -> RunRecord:
    return RunRecord(text="t", agent_id="agent:x", read_by=ReadBy.PARSER, offer_id="off_1", **fields)


@pytest.mark.parametrize(("order", "headline", "tone"), [
    (_order(OrderStatus.ORDERED, PlacedBy.AGENT), "Ordered by the agent", "ok"),
    (_order(OrderStatus.ORDERED, PlacedBy.HUMAN_APPROVAL), "Ordered with human approval", "ok"),
    (_order(OrderStatus.PENDING_APPROVAL), "Sent for approval", "warn"),
    (_order(OrderStatus.REJECTED), "Rejected by a human", "bad"),
    (_order(OrderStatus.EXPIRED), "Expired before a human decided", "bad"),
])
def test_an_order_has_a_headline_for_each_state_and_the_gateways_sentence(order: Any, headline: str, tone: str) -> None:
    outcome = outcome_of_order(order)

    assert (outcome.headline, outcome.tone, outcome.sentence) == (headline, tone, "What the gateway says.")
    assert outcome_of_run(OFFER, order, None) == outcome


@pytest.mark.parametrize(("fired", "headline"), [
    (("F-10",), "Prepared: confirm to order"),
    (("P-01", "P-03"), "Sent for approval"),
    (("P-04",), "Sent for approval"),
])
def test_an_order_only_f10_holds_back_is_prepared_and_waits_for_one_confirmation(
    fired: tuple[str, ...], headline: str
) -> None:
    """P8 F1: the agent prepared it and no other rule asked for a person, so the headline says so."""
    order = _order(OrderStatus.PENDING_APPROVAL, fired=fired)
    order.status_sentence = (
        "Prepared: confirm to order. Waiting for the purchasing manager to confirm, by Sunday 15 November 2026 at "
        "17:00 (UTC+02:00) (rule F-10: a person confirms every order)."
    )

    outcome = outcome_of_order(order)

    assert (outcome.headline, outcome.tone) == (headline, "warn")
    if headline.startswith("Prepared"):  # the opening is the headline, said once
        assert outcome.sentence.startswith("Waiting for the purchasing manager to confirm")
    else:
        assert outcome.sentence == order.status_sentence


def test_an_order_the_gateway_refused_is_said_with_its_reason() -> None:
    refusal = Problem(title="The policy does not allow this order", detail="A line declares milk (F-02).", status=422)

    outcome = outcome_of_run(OFFER, None, _record(not_ordered=refusal))

    assert (outcome.headline, outcome.tone) == ("No order was placed", "bad")
    assert outcome.sentence == "The policy does not allow this order. A line declares milk (F-02)."


def test_an_agent_that_ordered_nothing_speaks_for_itself() -> None:
    run = AgentRun(text="t", model="m", recorded=True, offer_id="off_1", report="I stopped: the offer is blocked.")

    outcome = outcome_of_run(OFFER, None, _record(agent_run=run))

    assert (outcome.headline, outcome.sentence) == ("No order was placed", "I stopped: the offer is blocked.")


def test_an_offer_nobody_ordered_from_says_so() -> None:
    outcome = outcome_of_run(OFFER, None, None)

    assert (outcome.headline, outcome.sentence) == ("No order was placed", "No order has been placed on this offer.")


def test_an_offer_with_no_option_has_nothing_to_order() -> None:
    outcome = outcome_of_run(EMPTY_OFFER, None, _record())

    assert outcome.headline == "Nothing to order"
    assert "No option could be built" in outcome.sentence
