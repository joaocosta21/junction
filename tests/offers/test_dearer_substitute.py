"""Decision B60 on the recording: a dearer substitute does not go through alone.

Found on the running system: with ordering alone switched on, 100 L of the lactose-free milk drink 469330
(8.54 euros for a case of 5 L: 1.71 a litre) were filled by 469363 at 2.48 a litre, judged replaceable, by the
agent alone: 248.00 against 170.80 euros, 45% more, and no rule fired. The stand-in line now carries what the
product asked for would have cost for the same content, and rule P-05 sends it to a person.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any

from tta.contracts.common import Identity, OptionKind, Unit, Verdict
from tta.contracts.policy import BuyerProfile
from tta.contracts.product import PackSize, ReplaceVerdict
from tta.offers import OfferService
from tta.offers.stand_ins import original_net_of
from tta.policy import RulePolicyEngine

ASKED_FOR, STAND_IN = "469330", "469363"


class _OrdersAlone:
    """The shipped policy, with ordering alone switched on for every profile. Nothing else differs."""

    def __init__(self, inner: RulePolicyEngine) -> None:
        self._inner = inner

    def get_profile(self, profile_id: str) -> BuyerProfile:
        return self._inner.get_profile(profile_id).model_copy(update={"auto_order_enabled": True})

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def test_a_substitute_45_percent_dearer_goes_to_a_person_with_ordering_alone_on(
    replay_deps: Any, policy: RulePolicyEngine, make_request: Any, agent_hotel: Identity
) -> None:
    service = OfferService(replace(replay_deps, policy=_OrdersAlone(policy)))

    offer = service.build_offer(make_request(100, Unit.L, product_ids=(ASKED_FOR,)), agent_hotel)

    option = next(each for each in offer.options if each.kind is OptionKind.SUBSTITUTE)
    line = option.lines[0]
    assert (line.product_id, line.quantity, str(line.net)) == (STAND_IN, 100, "248.00")
    assert line.substitute.replaceable.verdict is ReplaceVerdict.REPLACEABLE
    assert str(line.substitute.original_net) == "170.80"  # 100 L at 8.54 euros for 5 L
    # Before: AUTO, no rule fired.
    assert option.decision.verdict is Verdict.APPROVAL and option.decision.rule_ids == ("P-05",)
    assert option.decision.fired[0].sentence == (
        "Arla Semi skimmed milkdrink 1 L UHT lactose free Suomesta (469363) replaces 5 x Arla 1 L lactose free "
        "semi-skimmed milk drink Suomesta ESL (469330), and the substitute costs €77.20 more than the product you "
        "asked for (45.1% more): a person decides."
    )


def test_a_substitute_within_the_share_the_buyer_accepts_is_still_ordered_alone(
    fake_gateway: Any, deps_for: Any, policy: RulePolicyEngine, make_request: Any, agent_hotel: Identity,
    price: Any, stock: Any,
) -> None:
    """The autonomous path stays. The same two products, the stand-in at 2.00 euros a litre: 17% more, under the
    25% that holds where the profile sets no share of its own."""
    prices = [price(ASKED_FOR, "8.54", per_measure="1.708"), price(STAND_IN, "2.00")]
    lines = [stock(ASKED_FOR, None), stock(STAND_IN, 500)]
    service = OfferService(replace(deps_for(fake_gateway(prices, lines)), policy=_OrdersAlone(policy)))

    offer = service.build_offer(make_request(100, Unit.L, product_ids=(ASKED_FOR,)), agent_hotel)

    option = next(each for each in offer.options if each.kind is OptionKind.SUBSTITUTE)
    line = option.lines[0]
    assert (line.product_id, str(line.net), str(line.substitute.original_net)) == (STAND_IN, "200.00", "170.80")
    assert option.decision.verdict is Verdict.AUTO and option.decision.fired == ()

def test_what_the_product_asked_for_would_have_cost_is_taken_per_litre_or_kilogram() -> None:
    litre = PackSize(value=Decimal(1), unit=Unit.L, source="PRICE_RATIO")
    case = PackSize(value=Decimal(5), unit=Unit.L, source="PRICE_RATIO")
    kilo = PackSize(value=Decimal(1), unit=Unit.KG, source="PRICE_RATIO")

    assert original_net_of(Decimal("8.54"), case, litre, Decimal(100)) == Decimal("170.80")
    assert original_net_of(Decimal("1.71"), litre, case, Decimal(3)) == Decimal("25.65")  # 15 L at 1.71
    # Not known, never guessed: no price, a pack size that is not known, or litres against kilograms.
    assert original_net_of(None, case, litre, Decimal(100)) is None
    assert original_net_of(Decimal("8.54"), PackSize(), litre, Decimal(100)) is None
    assert original_net_of(Decimal("8.54"), case, PackSize(), Decimal(100)) is None
    assert original_net_of(Decimal("8.54"), case, kilo, Decimal(100)) is None
