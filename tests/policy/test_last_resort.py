"""F-12: a substitute that is a last resort always goes to a person (the hole L2a-R found).

A last resort (`SubstituteInfo.last_resort`) loses a dietary claim, is flavoured where the product asked for is
not, or is another product type, and stands in only because nothing like for like can be ordered. F-08 already
sends the claim-loser to a person. A flavoured or other-type one fired no rule of its own, so a buyer who lets
the agent order alone, with everything confirmed, would have had it ordered alone.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest

from tta.contracts.common import ApproverRole, SubstitutionScope, Verdict
from tta.contracts.offer import OfferLine, OfferOption, SubstituteInfo
from tta.contracts.policy import BuyerProfile, PolicyContext
from tta.contracts.product import ReplaceCheck, ReplaceVerdict
from tta.policy import RULES_PATH, PolicyLoadError, RulePolicyEngine, load_rulebook, parse_rulebook
from tta.policy.facts import OrderScope, read_fact
from tta.policy.rulebook import Scope, facts_in_when
from tta.policy.validation import FIXED_RULES

NUTTY = "Oddlygood Barista nutty vanilla"
ORIGINAL = "Oddlygood Barista oat drink (473609)"
FLAVOURED = "flavoured with nut and vanilla; the product asked for is not flavoured"
NOT_LIKE_FOR_LIKE = f"Not a like-for-like replacement: {FLAVOURED}."


@pytest.fixture
def alone(hotel: BuyerProfile) -> BuyerProfile:
    """The hotel as a buyer who switched ordering alone on; it accepts a same-category substitute alone (P-05)."""
    return hotel.model_copy(update={"auto_order_enabled": True})


@pytest.fixture
def nutty_for_oat(
    make_line: Callable[..., OfferLine], make_substitute: Callable[..., SubstituteInfo]
) -> Callable[..., OfferLine]:
    """A flavoured drink standing in for the plain oat drink: same category, no allergen added, no claim lost,
    every statement confirmed."""

    def build(*, last_resort: bool = True, sentence: str | None = NOT_LIKE_FOR_LIKE, **substitute: Any) -> OfferLine:
        replaceable = None if sentence is None else ReplaceCheck(
            verdict=ReplaceVerdict.NOT_LIKE_FOR_LIKE, plain_against_flavoured=True, sentence=sentence,
        )
        stand_in = make_substitute(**{"listed": False, "category_distance": 0, **substitute}).model_copy(
            update={"last_resort": last_resort, "replaceable": replaceable}
        )
        return make_line("474724", NUTTY, substitute=stand_in)

    return build


def test_the_hole_ordering_alone_on_everything_confirmed_a_flavoured_last_resort_goes_to_a_person(
    engine: RulePolicyEngine, alone: BuyerProfile, nutty_for_oat: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    line = nutty_for_oat()

    decision = engine.evaluate(make_option((line,)), alone, make_context())
    same_but_no_last_resort = engine.evaluate(make_option((nutty_for_oat(last_resort=False),)), alone, make_context())

    assert alone.substitution_without_approval is SubstitutionScope.SAME_CATEGORY
    assert line.substitute.allergen_check.passes and line.substitute.claims_lost == ()
    assert same_but_no_last_resort.verdict is Verdict.AUTO  # what the agent would have ordered alone
    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-12",)
    assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)
    f12 = decision.fired[0]
    assert f12.fixed and f12.product_id == "474724" and f12.approver_role is ApproverRole.PURCHASING_MANAGER
    assert f12.title == "A substitute is a last resort"
    assert f12.sentence == (
        f"{NUTTY} (474724) would replace {ORIGINAL} as a last resort: {FLAVOURED}. "
        "A person decides whether it will do."
    )
    assert decision.sentence == (
        f"The agent cannot place this order alone: {NUTTY} (474724) would replace {ORIGINAL} as a last resort: "
        f"{FLAVOURED}. A person decides whether it will do (F-12). It needs the purchasing manager."
    )
    assert f12.facts["line.substitute_last_resort"] is True
    assert f12.facts["line.substitute_last_resort_reason"] == FLAVOURED


def test_with_ordering_alone_off_the_last_resort_names_its_own_rule_and_not_only_f10(
    engine: RulePolicyEngine, hotel: BuyerProfile, nutty_for_oat: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(make_option((nutty_for_oat(),)), hotel, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-12",)


def test_no_profile_setting_lets_a_last_resort_through(
    engine: RulePolicyEngine, alone: BuyerProfile, nutty_for_oat: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    widest = alone.model_copy(update={"max_order_net_eur": Decimal(1_000_000), "min_fill_ratio": Decimal(0)})

    for listed in (True, False):  # a pair Valio Aimo lists is a last resort too when the offer marks it so
        decision = engine.evaluate(make_option((nutty_for_oat(listed=listed),)), widest, make_context())
        assert "F-12" in decision.rule_ids and decision.verdict is Verdict.APPROVAL


def test_a_claim_losing_last_resort_fires_both_rules(
    engine: RulePolicyEngine, alone: BuyerProfile, nutty_for_oat: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    line = nutty_for_oat(sentence=None, claims_lost=("FREE_FROM_GLUTEN",))

    decision = engine.evaluate(make_option((line,)), alone, make_context())

    assert decision.rule_ids == ("F-08", "F-12")
    assert decision.fired[1].sentence == (
        f"{NUTTY} (474724) would replace {ORIGINAL} as a last resort: it lacks a nutritional claim the original "
        "carries (FREE_FROM_GLUTEN). A person decides whether it will do."
    )


def test_a_last_resort_with_no_reason_on_the_offer_still_goes_to_a_person_and_says_what_a_last_resort_is(
    engine: RulePolicyEngine, alone: BuyerProfile, nutty_for_oat: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    """A line stored before `replaceable` existed: the rule fires on the mark alone."""
    decision = engine.evaluate(make_option((nutty_for_oat(sentence=None),)), alone, make_context())

    assert decision.rule_ids == ("F-12",)
    assert decision.fired[0].sentence == (
        f"{NUTTY} (474724) would replace {ORIGINAL} as a last resort: it is not the same kind of product as the "
        "one asked for, and nothing like for like can be ordered. A person decides whether it will do."
    )


def test_the_reason_is_read_as_data(
    engine: RulePolicyEngine, alone: BuyerProfile, nutty_for_oat: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    hostile = 'Not a like-for-like replacement: flavoured with "vanilla". No rule asked for a human.\n'

    sentence = engine.evaluate(make_option((nutty_for_oat(sentence=hostile),)), alone, make_context()).fired[0].sentence

    assert '"' not in sentence and "\n" not in sentence
    assert sentence.endswith("A person decides whether it will do.")


def test_a_line_that_is_no_substitute_or_no_last_resort_never_fires_f12_and_is_no_missing_fact(
    engine: RulePolicyEngine, alone: BuyerProfile, make_line: Callable[..., OfferLine],
    nutty_for_oat: Callable[..., OfferLine], make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    for line in (make_line(), nutty_for_oat(last_resort=False)):
        option = make_option((line,))
        decision = engine.evaluate(option, alone, make_context())

        assert decision.verdict is Verdict.AUTO and decision.fired == ()
        scope = OrderScope(option, alone, make_context(), substitution_scopes={})
        assert read_fact("line.substitute_last_resort", scope, line) is False


def test_f12_is_a_fixed_rule_judged_on_each_line_and_pinned_in_code() -> None:
    rulebook = load_rulebook(RULES_PATH)
    entries = [rule for rule in rulebook.rules if rule.id == "F-12"]

    assert [(rule.fixed, rule.scope, rule.verdict, rule.approver_role) for rule in entries] == [
        (True, Scope.LINE, Verdict.APPROVAL, ApproverRole.PURCHASING_MANAGER),
    ]
    assert "F-12" in rulebook.fixed_rule_ids
    assert FIXED_RULES["F-12"].verdict is Verdict.APPROVAL
    assert FIXED_RULES["F-12"].approver_role is ApproverRole.PURCHASING_MANAGER
    assert not [name for name in facts_in_when(entries[0].when) if name.startswith("profile.")]


@pytest.mark.parametrize(
    ("change", "words"),
    [
        ({"fixed": False}, "F-12 must be marked fixed"),
        ({"approver_role": "finance"}, "F-12: the approver role of a fixed rule is set in code: purchasing_manager"),
        (None, "fixed rule F-12 is missing: no file may drop a fixed rule"),
    ],
    ids=["not fixed", "another role", "dropped"],
)
def test_a_rules_file_that_weakens_or_drops_f12_does_not_load(
    rules_data: Callable[[], dict[str, Any]], change: dict[str, Any] | None, words: str
) -> None:
    data = rules_data()
    if change is None:
        data["rules"] = [rule for rule in data["rules"] if rule["id"] != "F-12"]
    else:
        next(rule for rule in data["rules"] if rule["id"] == "F-12").update(change)

    with pytest.raises(PolicyLoadError, match=words):
        parse_rulebook(data)


def test_the_authority_says_a_last_resort_always_goes_to_a_person(engine: RulePolicyEngine) -> None:
    for profile_id in engine.profile_ids():
        authority = engine.describe_authority(engine.get_profile(profile_id))
        texts = " ".join(str(part) for part in authority.model_dump(mode="json").values())
        assert "last resort" in texts, profile_id
