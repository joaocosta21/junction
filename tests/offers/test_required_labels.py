"""A request line can require certificate labels, as it requires nutritional claims (task SUST-1).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for": a product without a
required label is not a candidate, and each option carries one constraint check per label.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from tta.contracts.common import CheckResult, ConstraintKind, Identity, Unit
from tta.contracts.offer import ConstraintCheck, Offer, OfferOption
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.offers import OfferService

MONDAY = date(2026, 11, 16)
ORGANIC = "EU_ORGANIC_FARMING"
ORGANIC_OAT_DRINK = "460825"  # Oatly Oat Drink Organic 1L: €1.74, 177 confirmed in tonight's capture
RELIABLE_OAT = "470863"  # carries no certificate label


def request(*, product_type: str | None = "plant_drink", product_ids: tuple[str, ...] = ()) -> PurchaseRequest:
    return PurchaseRequest(
        needed_by=MONDAY,
        lines=(RequestLine(
            text="100 litres of organic oat drink by Monday", product_type=product_type, product_ids=product_ids,
            required_labels=(ORGANIC,), quantity=Decimal(100), unit=Unit.L,
        ),),
    )


def label_checks(option: OfferOption) -> list[ConstraintCheck]:
    return [check for check in option.constraint_checks if check.kind is ConstraintKind.LABEL]


def test_only_products_with_the_label_are_candidates(service: OfferService, agent_hotel: Identity) -> None:
    offer: Offer = service.build_offer(request(), agent_hotel)
    first = offer.options[0]

    assert first.product_ids == (ORGANIC_OAT_DRINK,)
    assert first.totals.net == Decimal("174.00")
    assert all(ORGANIC in line.labels for option in offer.options for line in option.lines)
    assert RELIABLE_OAT not in {exclusion.product_id for exclusion in offer.excluded}
    assert offer.candidates_considered < 51  # the 51 plant drinks without the label filter


def test_one_label_check_per_label_met_by_every_line(service: OfferService, agent_hotel: Identity) -> None:
    (check,) = label_checks(service.build_offer(request(), agent_hotel).options[0])

    assert check.subject == ORGANIC
    assert check.result is CheckResult.MET
    assert check.sentence == f"Every product offered carries the certificate label {ORGANIC}."


def test_a_named_product_without_the_label_fails_the_check(service: OfferService, agent_hotel: Identity) -> None:
    offer = service.build_offer(request(product_type=None, product_ids=(RELIABLE_OAT,)), agent_hotel)
    (check,) = label_checks(offer.options[0])

    assert check.result is CheckResult.NOT_MET
    assert check.sentence == f"Without the certificate label {ORGANIC}: {RELIABLE_OAT}."
