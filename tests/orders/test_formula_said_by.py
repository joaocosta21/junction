"""At order time the formula rule says who said the formula matters: the request, or what the gateway learned.

In the buyer's mode LEARN the gateway adds the request's mark itself, on a line whose product it learned the recipe
matters for; the offer line carries `keep_formula` and the offer keeps the request as the buyer sent it. The order
book judges the option again when the order is placed, and tells rule F-11 that request (`tta.orders.checking`),
so the order's decision, its approval and its log never say "the request says so" for a mark the request did not
carry (browser walk of Sunday 15 Nov 2026).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from tta.contracts.common import Identity, OrderStatus
from tta.contracts.product import FormulaCheck, FormulaOutcome, NutrientDifference, ReplaceCheck, ReplaceVerdict

MATTERS = "where the formula matters"
LEARNED = f"{MATTERS} (what the agent learned about the orders of Harbourside Hotel says so for this line)"
ASKED = f"{MATTERS} (the request says so for this line)"
DIFFERENT = FormulaCheck(
    outcome=FormulaOutcome.DIFFERENT,
    differences=(NutrientDifference(nutrient="fat", original=Decimal(36), other=Decimal(15), within_tolerance=False),),
    sentence="Different formula: fat 15 g, not 36 g per 100 g.",
)
OTHER_FORMULA = "a different formula (fat 15 g, not 36 g)"


def _option(samples: Any) -> Any:
    """A cooking blend for a whipping cream, with the mark that the formula matters on its line."""
    check = ReplaceCheck(
        verdict=ReplaceVerdict.NOT_LIKE_FOR_LIKE, reasons=(OTHER_FORMULA,),
        sentence=f"Not a like-for-like replacement: {OTHER_FORMULA}.",
    )
    stand_in = samples.substitute().model_copy(update={"formula": DIFFERENT, "replaceable": check})
    line = samples.line("463975", "100", "2.00", substitute=stand_in).model_copy(update={"keep_formula": True})
    return samples.option("opt_1", (line,))


@pytest.mark.parametrize(
    ("request_says", "said"), [(None, LEARNED), (True, ASKED)], ids=["added by the gateway", "said by the request"]
)
def test_the_order_says_who_said_the_formula_matters(
    book: Any, samples: Any, agent_hotel: Identity, request_says: bool | None, said: str
) -> None:
    offer = book.offer(_option(samples))
    line = offer.request.lines[0].model_copy(update={"keep_formula": request_says})
    book.store.save_offer(offer.model_copy(update={"request": offer.request.model_copy(update={"lines": (line,)})}))

    order = book.service.place_order(offer.offer_id, "opt_1", agent_hotel, "formula-1")

    assert order.status is OrderStatus.PENDING_APPROVAL and order.decision.rule_ids == ("F-11",)
    f11 = order.decision.fired[0]
    assert said in f11.sentence and said in order.decision.sentence
    assert f11.facts["line.formula_matters_reason"] == said.removeprefix(f"{MATTERS} (").removesuffix(")")
    approval = book.store.get_approval(order.approval_id)
    assert any(said in reason for reason in approval.reasons)
    (requested,) = book.events(order.order_id)
    assert said in requested.data.sentence  # the log quotes the rule's sentence as the engine wrote it
    assert ("the request says so" in order.decision.sentence) is (request_says is True)
