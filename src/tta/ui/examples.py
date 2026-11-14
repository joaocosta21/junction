"""The four demo requests of the first page, each with its typed request (PLAN section 3, SPEC section 13).

Scores on the 30% "working end-to-end demo": one click runs request -> lookup -> offer -> order or approval.
An example carries the typed request its sentence stands for, so the demo never depends on a model being
reachable: with no parser and no buyer agent, the page still runs the three scenarios and the fourth example.
The fourth (task T18, asked by the orchestrator) shows the dietitian's approval: an oat drink whose milk Valio's
file says nothing about, under a strict no-milk rule.

The typed requests name Monday 16 November 2026: the Monday after the replay capture (Saturday 14 November)
and the Monday of the event. A sentence that is not one of these four is read by the parser, never by us.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from tta.contracts.common import AllergenStrictness, Unit
from tta.contracts.request import PurchaseRequest, RequestLine

MONDAY = date(2026, 11, 16)
HOTEL_AGENT = "agent:hotel-kitchen"
WARD_AGENT = "agent:allergy-ward"
# GS1 allergen codes: AM is milk, AW is cereals containing gluten (AIMO/docs/SCHEMA-AND-CODES.md).
MILK, GLUTEN = "AM", "AW"
# Oddlygood Barista oat drink 1 l, gluten free: its quantity is not confirmed in the capture, and two of the
# three substitutes Valio lists for it add gluten (AIMO/FINDINGS.md, scenario 3).
OAT_DRINK = "473609"
# Elovena barista oat drink 1 l: confirmed in tonight's capture (100 L for €208.00), and Valio's file states nothing
# about milk, so under a strict no-milk rule rule P-04 sends it to the dietitian (run in replay on 14 Nov 2026).
ELOVENA_OAT_DRINK = "469512"

SCENARIO_1_TEXT = "1,000 litres of lactose-free milk by Monday"
SCENARIO_2_TEXT = "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only"
SCENARIO_3_TEXT = f"100 litres of Oddlygood Barista oat drink, product {OAT_DRINK}, by Monday"
DIETITIAN_TEXT = (
    f"100 litres of Elovena barista oat drink, product {ELOVENA_OAT_DRINK}, by Monday; no milk, strict rule"
)


@dataclass(frozen=True)
class Example:
    """One demo request: what is pasted, who asks, and the typed request the sentence stands for."""

    key: str
    label: str
    shows: str  # one sentence: what this scenario demonstrates
    text: str
    agent_id: str
    request: PurchaseRequest


EXAMPLES: tuple[Example, ...] = (
    Example(
        key="scenario-1",
        label="Scenario 1 · hotel kitchen",
        shows="No single confirmed product covers it: a confirmed option, a cheaper unconfirmed one, a human decides.",
        text=SCENARIO_1_TEXT,
        agent_id=HOTEL_AGENT,
        request=PurchaseRequest(
            needed_by=MONDAY,
            lines=(RequestLine(
                text=SCENARIO_1_TEXT, product_type="milk", required_claims=("FREE_FROM_LACTOSE",),
                quantity=Decimal(1000), unit=Unit.L,
            ),),
        ),
    ),
    Example(
        key="scenario-2",
        label="Scenario 2 · allergy ward",
        shows="Strict allergen rule, confirmed data only, within the spend limit: the agent orders alone.",
        text=SCENARIO_2_TEXT,
        agent_id=WARD_AGENT,
        request=PurchaseRequest(
            needed_by=MONDAY,
            require_confirmed=True,
            lines=(RequestLine(
                text=SCENARIO_2_TEXT, product_type="plant_drink", quantity=Decimal(200), unit=Unit.L,
                exclude_allergens=(MILK, GLUTEN),
            ),),
        ),
    ),
    Example(
        key="scenario-3",
        label="Scenario 3 · substitutes",
        shows="The product asked for is not confirmed: its substitutes are ranked, and two of Valio's own fail.",
        text=SCENARIO_3_TEXT,
        agent_id=HOTEL_AGENT,
        request=PurchaseRequest(
            needed_by=MONDAY,
            lines=(RequestLine(
                text=SCENARIO_3_TEXT, product_ids=(OAT_DRINK,), quantity=Decimal(100), unit=Unit.L,
            ),),
        ),
    ),
    Example(
        key="scenario-4",
        label="Dietitian: oat drink with no milk statement",
        shows="Confirmed and within the limits, but Valio's data says nothing about milk: the dietitian decides.",
        text=DIETITIAN_TEXT,
        agent_id=HOTEL_AGENT,
        request=PurchaseRequest(
            needed_by=MONDAY,
            lines=(RequestLine(
                text=DIETITIAN_TEXT, product_ids=(ELOVENA_OAT_DRINK,), quantity=Decimal(100), unit=Unit.L,
                exclude_allergens=(MILK,), allergen_strictness=AllergenStrictness.STRICT,
            ),),
        ),
    ),
)


def _folded(text: str) -> str:
    return " ".join(text.split()).casefold()


_BY_KEY = {example.key: example for example in EXAMPLES}
_BY_TEXT = {_folded(example.text): example for example in EXAMPLES}


def example_by_key(key: str) -> Example | None:
    return _BY_KEY.get(key)


def example_for_text(text: str) -> Example | None:
    """The example whose sentence this is, whatever the spacing and the case. Any other text: `None`."""
    return _BY_TEXT.get(_folded(text))
