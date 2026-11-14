"""The demo requests of the first page, each with its typed request (PLAN section 5, SPEC section 13).

Scores on the 30% "working end-to-end demo": one click runs request -> lookup -> offer -> order or approval.
An example carries the typed request its sentence stands for, so the demo never depends on a model being
reachable: with no parser and no buyer agent, the page still runs every example.

They come in the order of the demo set (docs/DEMO.md), each with its customer: 1 the brief's own request (hotel),
2 the ward's strict allergen rules, 3 a supplier stock-out (hotel), 4 a product with an allergen doubt (the hotel's
oat drink with no milk statement, then the school's almond drink, which the manufacturer's page says contains
almond), 5 the customer's pattern (the hotel's usual 100 L of milk, then its standing order at 290 L on the
standing-order page: scenario 7), 6 formula matters (the bakery's crème fraîche, whose only substitutes change the
formula, then its whipping cream). Then the reserve: the reliability preference (task SUST-1). An example whose
customer has no demo agent on the page is not shown.

Every typed request is what the fixed-rules reader reads from its sentence (tests/e2e and
tests/agent/test_reading_table.py hold the two together). The sentences are short on purpose: together they stay
under 600 characters.

The typed requests name Monday 16 November 2026: the Monday after the replay capture (Saturday 14 November)
and the Monday of the event. A sentence that is not one of these is read by the parser, never by us.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from tta.contracts.common import AllergenStrictness, Preference, Unit
from tta.contracts.request import PurchaseRequest, RequestLine

MONDAY = date(2026, 11, 16)
HOTEL_AGENT = "agent:hotel-kitchen"
WARD_AGENT = "agent:allergy-ward"
SCHOOL_AGENT = "agent:school-kitchen"
BAKERY_AGENT = "agent:bakery-cafe"
# GS1 allergen codes: AM is milk, AW is cereals containing gluten (AIMO/docs/SCHEMA-AND-CODES.md).
MILK, GLUTEN = "AM", "AW"
# Oddlygood Barista oat drink 1 l, gluten free: its quantity is not confirmed in the capture, and two of the
# three substitutes Valio lists for it add gluten (AIMO/FINDINGS.md, scenario 3).
OAT_DRINK = "473609"
# Elovena barista oat drink 1 l: confirmed in tonight's capture (100 L for €208.00), and Valio's file states nothing
# about milk, so under a strict no-milk rule rule P-04 sends it to the dietitian (run in replay on 14 Nov 2026).
ELOVENA_OAT_DRINK = "469512"
# Valio crème fraîche 2 kg, lactose free: its quantity is not confirmed in the capture, and no substitute that
# keeps its formula can be ordered, so rule F-11 fires on the one that is offered (run in replay on 14 Nov 2026).
CREME_FRAICHE = "477055"
# Tonight's capture, run in replay on 14 Nov 2026 (task SUST-1): by price, 100 L of oat drink is 472145 (Oatly No
# Sugars, €133.00, no delivery-reliability value); ranked by delivery reliability it is 470863 (Oatly Semi, €140.00,
# reliability 1.0), and 472145 stays on the table as the cheapest confirmed option.

SCENARIO_1_TEXT = "1,000 litres of lactose-free milk by Monday"
SCENARIO_2_TEXT = "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only"
SCENARIO_3_TEXT = f"100 litres of Oddlygood Barista oat drink, product {OAT_DRINK}, by Monday"
DIETITIAN_TEXT = (
    f"100 litres of Elovena barista oat drink, product {ELOVENA_OAT_DRINK}, by Monday; no milk, strict rule"
)
RELIABLE_TEXT = "100 litres of oat drink by Monday, most reliable delivery"
# The hotel's usual weekly milk, 469363, the product of its standing order (tta.ui.standing_page): run in replay on
# 14 Nov 2026 at the recording's clock, 100 x 469363 for €248.00, to a person.
PATTERN_TEXT = "100 litres of lactose-free milk by Monday"
# Run as the hotel in replay on 14 Nov 2026: confirmed whipping cream is 48 x 469346 + 37 x 464727, 85 L in all, so
# 100 L is short. Vegetable-fat blends are a product type of their own and never top cream up (product_types.yaml).
FORMULA_TEXT = "100 litres of whipping cream by Monday, for cakes"
FORMULA_CHANGED_TEXT = f"40 kg of Valio crème fraîche, product {CREME_FRAICHE}, by Monday, for baking"
# The school's profile excludes tree nuts, peanuts and sesame under the strict rule, so the sentence names none. Run
# in replay on 14 Nov 2026: 20 x 465793 (Alpro Barista Almond) for €47.60, to the dietitian (P-04), with the
# manufacturer's page attached, which says the drink contains almond.
ALMOND_TEXT = "20 litres of almond drink by Monday"
STANDING_ORDERS = "/standing-orders"


@dataclass(frozen=True)
class Example:
    """One demo request: what is pasted, who asks, and the typed request the sentence stands for."""

    key: str
    label: str
    shows: str  # one sentence: what this scenario demonstrates
    text: str
    agent_id: str
    request: PurchaseRequest
    step: int | None = None  # its place in the demo set; None: a reserve example
    then: tuple[str, str] | None = None  # where the scenario goes on, and the words of the link


EXAMPLES: tuple[Example, ...] = (
    Example(
        key="scenario-1",
        label="The brief's own request",
        shows="Confirmed stock covers 435 of the 1,000 L: the confirmed part, or all of it from a product whose "
        "quantity is not confirmed. A person decides.",
        text=SCENARIO_1_TEXT,
        agent_id=HOTEL_AGENT,
        step=1,
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
        label="Strict allergen rules",
        shows="No milk, no gluten, confirmed data only: one safe product within the limits, and a person confirms "
        "the order.",
        text=SCENARIO_2_TEXT,
        agent_id=WARD_AGENT,
        step=2,
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
        label="A supplier stock-out",
        shows="Valio Aimo does not confirm the stock of the product asked for: its substitutes are ranked with "
        "what each gives up, and two of Valio's own listed substitutes are refused because they add gluten.",
        text=SCENARIO_3_TEXT,
        agent_id=HOTEL_AGENT,
        step=3,
        request=PurchaseRequest(
            needed_by=MONDAY,
            lines=(RequestLine(
                text=SCENARIO_3_TEXT, product_type="plant_drink", product_ids=(OAT_DRINK,), quantity=Decimal(100),
                unit=Unit.L,
            ),),
        ),
    ),
    Example(
        key="scenario-4",
        label="An allergen doubt",
        shows="Valio's data says nothing about milk for this oat drink: a product whose data rules milk out comes "
        "first, and the one asked for is a labelled alternative that only the dietitian can release.",
        text=DIETITIAN_TEXT,
        agent_id=HOTEL_AGENT,
        step=4,
        request=PurchaseRequest(
            needed_by=MONDAY,
            lines=(RequestLine(
                text=DIETITIAN_TEXT, product_type="plant_drink", product_ids=(ELOVENA_OAT_DRINK,),
                quantity=Decimal(100), unit=Unit.L, exclude_allergens=(MILK,),
                allergen_strictness=AllergenStrictness.STRICT,
            ),),
        ),
    ),
    Example(
        key="almond",
        label="The manufacturer's page adds a doubt",
        shows="The school excludes tree nuts. No almond drink's data rules them out, so nothing is suggested as "
        "safe: the dietitian decides, with the manufacturer's page attached as evidence.",
        text=ALMOND_TEXT,
        agent_id=SCHOOL_AGENT,
        step=4,
        request=PurchaseRequest(
            needed_by=MONDAY,
            lines=(RequestLine(
                text=ALMOND_TEXT, product_type="plant_drink", name_terms=("almond",), quantity=Decimal(20),
                unit=Unit.L,
            ),),
        ),
    ),
    Example(
        key="pattern",
        label="The customer's pattern",
        shows="The hotel's usual 100 L of milk, with the cooking cream it usually orders with it and Valio Aimo's "
        "own suggestion. Then its weekly standing order, renewed at 290 L against a usual 100 L, goes to a person.",
        text=PATTERN_TEXT,
        agent_id=HOTEL_AGENT,
        step=5,
        then=(STANDING_ORDERS, "Renew the hotel's standing order: the usual 100 L, then 290 L"),
        request=PurchaseRequest(
            needed_by=MONDAY,
            lines=(RequestLine(
                text=PATTERN_TEXT, product_type="milk", required_claims=("FREE_FROM_LACTOSE",),
                quantity=Decimal(100), unit=Unit.L,
            ),),
        ),
    ),
    Example(
        key="formula-changed",
        label="Formula matters",
        shows="The crème fraîche asked for is not confirmed, and no substitute keeps its formula: the one there is "
        "comes only as a labelled alternative for a person, with the difference in grams.",
        text=FORMULA_CHANGED_TEXT,
        agent_id=BAKERY_AGENT,
        step=6,
        request=PurchaseRequest(
            needed_by=MONDAY,
            lines=(RequestLine(
                text=FORMULA_CHANGED_TEXT, product_ids=(CREME_FRAICHE,), quantity=Decimal(40), unit=Unit.KG,
                keep_formula=True,
            ),),
        ),
    ),
    Example(
        key="formula",
        label="Formula kept",
        shows="Less whipping cream is confirmed than the bakery needs: the offer says what is short and never tops "
        "it up with a vegetable-fat blend.",
        text=FORMULA_TEXT,
        agent_id=BAKERY_AGENT,
        step=6,
        request=PurchaseRequest(
            needed_by=MONDAY,
            lines=(RequestLine(
                text=FORMULA_TEXT, product_type="cream", name_terms=("whipping",), quantity=Decimal(100),
                unit=Unit.L, keep_formula=True,
            ),),
        ),
    ),
    Example(
        key="scenario-5",
        label="Most reliable delivery",
        shows="Reliability first: a product with a 100% delivery record beats a cheaper one with none, "
        "and the cheaper one stays on the table with the difference in euros.",
        text=RELIABLE_TEXT,
        agent_id=HOTEL_AGENT,
        request=PurchaseRequest(
            needed_by=MONDAY,
            prefer=Preference.RELIABILITY,
            lines=(RequestLine(
                text=RELIABLE_TEXT, product_type="plant_drink", name_terms=("oat",), quantity=Decimal(100),
                unit=Unit.L,
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
