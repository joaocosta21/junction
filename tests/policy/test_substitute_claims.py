"""F-08: a substitute that lacks a nutritional claim of the original always goes to a human (SPEC sections 5, 7).

A nutritional claim is not an allergen statement. Lactose-free milk and regular milk both declare milk, so the
allergen rule for substitutes (F-05) passes; what the buyer would lose is the claim, and a person decides that.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tta.contracts.common import AllergenRelation, ApproverRole, SubstitutionScope, Verdict
from tta.contracts.offer import OfferLine, OfferOption, SubstituteInfo
from tta.contracts.policy import BuyerProfile, PolicyContext
from tta.policy import PROFILES_DIR, RULES_PATH, PolicyLoadError, RulePolicyEngine, load_rulebook, parse_rulebook
from tta.policy.facts import OrderScope, read_fact
from tta.policy.rulebook import Scope, facts_in_when

LACTOSE_FREE = "FREE_FROM_LACTOSE"
# Catalog ids: 463149 carries no lactose-free claim, 469363 does (as in tests/offers/test_checks_and_edges.py).
REGULAR_MILK = "Valio Plus skimmed milk 1 l (463149)"
LACTOSE_FREE_MILK = "Arla Semi skimmed milkdrink 1 L UHT lactose free Suomesta (469363)"


@pytest.fixture
def regular_for_lactose_free(
    make_line: Callable[..., OfferLine], make_substitute: Callable[..., SubstituteInfo]
) -> Callable[..., OfferLine]:
    """Regular milk standing in for the lactose-free milk the buyer named by id: same category, no allergen added."""

    def build(claims_lost: tuple[str, ...] = (LACTOSE_FREE,), **substitute: Any) -> OfferLine:
        stand_in = make_substitute(listed=False, category_distance=0, claims_lost=claims_lost, **substitute)
        named = stand_in.model_copy(update={
            "original_id": "469363", "original_name": "Arla Semi skimmed milkdrink 1 L UHT lactose free Suomesta",
        })
        return make_line("463149", "Valio Plus skimmed milk 1 l", substitute=named)

    return build


def test_regular_milk_in_place_of_lactose_free_milk_goes_to_the_dietitian_the_hotel_names(
    engine: RulePolicyEngine, hotel: BuyerProfile, regular_for_lactose_free: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    """The case of the T07 hand-back: `hotel-kitchen` accepts a substitute of the same category alone."""
    line = regular_for_lactose_free()

    decision = engine.evaluate(make_option((line,)), hotel, make_context())

    assert hotel.substitution_without_approval is SubstitutionScope.SAME_CATEGORY
    assert line.substitute.allergen_check.passes  # the allergen rule sees nothing: both declare milk
    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-08",)
    assert decision.required_roles == (ApproverRole.DIETITIAN,)  # a nutrition question, and the hotel names one
    f08 = decision.fired[0]
    assert f08.fixed and f08.verdict is Verdict.APPROVAL and f08.product_id == "463149"
    assert f08.approver_role is ApproverRole.DIETITIAN
    assert f08.title == "A substitute lacks a nutritional claim the original carries"
    assert f08.sentence == (
        f"{REGULAR_MILK} would replace {LACTOSE_FREE_MILK} but is not marked lactose-free, as the product asked "
        "for is."
    )
    assert f08.facts == {
        "line.is_substitute": True,
        "line.substitute_claims_lost": ["FREE_FROM_LACTOSE"],  # the code is in the facts, the word in the sentence
        "line.name": "Valio Plus skimmed milk 1 l",
        "line.product_id": "463149",
        "line.substitute_original": LACTOSE_FREE_MILK,
        "line.substitute_claims_lost_said": "lactose-free",
        "profile.names_dietitian": True,  # what decided who signs
    }
    assert decision.sentence == (
        f"The agent cannot place this order alone: {REGULAR_MILK} would replace {LACTOSE_FREE_MILK} but is not "
        "marked lactose-free, as the product asked for is (F-08). It needs the dietitian."
    )


def test_a_buyer_that_names_no_dietitian_sends_the_lost_claim_to_the_purchasing_manager(
    engine: RulePolicyEngine, hotel: BuyerProfile, regular_for_lactose_free: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    """Who is asked follows the profile; that a person is asked does not: the rule fires either way."""
    roles = {role: ids for role, ids in hotel.approver_roles.items() if role is not ApproverRole.DIETITIAN}
    for named in (roles, {**roles, ApproverRole.DIETITIAN: ()}):  # no entry, and an entry that names nobody
        no_dietitian = hotel.model_copy(update={"approver_roles": named})

        decision = engine.evaluate(make_option((regular_for_lactose_free(),)), no_dietitian, make_context())

        assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-08",)
        assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)
        assert decision.fired[0].facts["profile.names_dietitian"] is False
        assert engine.describe_authority(no_dietitian).rules[6].sentence == (
            "A substitute that lacks a dietary claim of the product it replaces, for example lactose-free, always "
            "goes to the purchasing manager: Harbourside Hotel names no dietitian."
        )


def test_f08_names_every_claim_the_substitute_lacks(
    engine: RulePolicyEngine, hotel: BuyerProfile, regular_for_lactose_free: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    line = regular_for_lactose_free((LACTOSE_FREE, "LOW_FAT"))

    decision = engine.evaluate(make_option((line,)), hotel, make_context())

    assert decision.rule_ids == ("F-08",)
    # A code the table of dietary claims does not hold is said in lower case; the offer lists dietary claims only.
    assert decision.fired[0].sentence.endswith(
        "but is not marked lactose-free and low fat, as the product asked for is."
    )
    assert decision.fired[0].facts["line.substitute_claims_lost"] == ["FREE_FROM_LACTOSE", "LOW_FAT"]


def test_f08_is_silent_for_a_substitute_that_keeps_every_claim(
    engine: RulePolicyEngine, hotel: BuyerProfile, regular_for_lactose_free: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(make_option((regular_for_lactose_free(()),)), hotel, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-10",)


def test_a_line_that_is_not_a_substitute_never_fires_f08(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    line = make_line()
    option = make_option((line,))
    scope = OrderScope(option, hotel, make_context(), {})
    rule = next(rule for rule in load_rulebook(RULES_PATH).rules if rule.id == "F-08")

    assert line.substitute is None
    assert read_fact("line.substitute_claims_lost", scope, line) == ()
    assert "line.is_substitute" in facts_in_when(rule.when)  # the rule asks first whether the line replaces anything
    assert "F-08" not in engine.evaluate(option, hotel, make_context()).rule_ids


@pytest.mark.parametrize("scope", list(SubstitutionScope))
def test_no_substitution_setting_lets_the_agent_accept_a_lost_claim_alone(
    scope: SubstitutionScope, engine: RulePolicyEngine, hotel: BuyerProfile,
    regular_for_lactose_free: Callable[..., OfferLine], make_substitute: Callable[..., SubstituteInfo],
    make_line: Callable[..., OfferLine], make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    """Also for a substitute Valio Aimo lists itself: the widest setting accepts it, F-08 still asks a human."""
    profile = hotel.model_copy(update={"substitution_without_approval": scope})
    listed = make_line("471690", "Oat drink", substitute=make_substitute(listed=True, claims_lost=("VEGAN",)))

    for line in (regular_for_lactose_free(), listed):
        decision = engine.evaluate(make_option((line,)), profile, make_context())

        assert decision.verdict is Verdict.APPROVAL and "F-08" in decision.rule_ids
        assert ApproverRole.DIETITIAN in decision.required_roles


def test_f08_is_listed_before_the_profile_rule_about_substitutes(
    engine: RulePolicyEngine, hotel: BuyerProfile, regular_for_lactose_free: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    no_substitutes = hotel.model_copy(update={"substitution_without_approval": SubstitutionScope.NONE})

    decision = engine.evaluate(make_option((regular_for_lactose_free(),)), no_substitutes, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-08", "P-05")
    assert [rule.fixed for rule in decision.fired] == [True, False]
    # Two questions, two roles: the lost claim is the dietitian's, the substitute as such the purchasing manager's.
    assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER, ApproverRole.DIETITIAN)


def test_a_substitute_that_adds_an_allergen_stays_blocked_when_it_also_lacks_a_claim(
    engine: RulePolicyEngine, hotel: BuyerProfile, regular_for_lactose_free: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    line = regular_for_lactose_free(added=(("AE", AllergenRelation.MAY_CONTAIN),))

    decision = engine.evaluate(make_option((line,)), hotel, make_context())

    assert decision.verdict is Verdict.BLOCK and decision.rule_ids == ("F-05", "F-08")
    assert decision.required_roles == ()  # nobody can sign off a blocked order
    assert "(F-05)" in decision.sentence and "(F-08)" not in decision.sentence


# --- F-08 is a fixed rule: in the file, pinned in code, in the authority and in the hash ----------------------

def test_f08_is_a_fixed_rule_judged_on_each_line() -> None:
    rulebook = load_rulebook(RULES_PATH)
    entries = [rule for rule in rulebook.rules if rule.id == "F-08"]

    assert [(rule.fixed, rule.scope, rule.verdict, rule.approver_role) for rule in entries] == [
        (True, Scope.LINE, Verdict.APPROVAL, ApproverRole.PURCHASING_MANAGER),
    ]
    assert "F-08" in rulebook.fixed_rule_ids
    assert not [name for name in facts_in_when(entries[0].when) if name.startswith("profile.")]


def _f08(data: dict[str, Any]) -> dict[str, Any]:
    return next(rule for rule in data["rules"] if rule["id"] == "F-08")


def _break(data: dict[str, Any], case: str) -> None:
    if case == "removed":
        data["rules"].remove(_f08(data))
    elif case == "no longer fixed":
        _f08(data)["fixed"] = False
    elif case == "blocks instead":
        _f08(data)["verdict"] = "BLOCK"
        del _f08(data)["approver_role"]
    elif case == "another approver":
        _f08(data)["approver_role"] = "finance"
    elif case == "reads a profile setting":
        _f08(data)["when"]["all"].append({"fact": "profile.auto_order_enabled", "op": "is_false"})
    elif case == "judged per order":
        _f08(data)["scope"] = "order"
    else:  # pragma: no cover
        raise AssertionError(case)


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("removed", "fixed rule F-08 is missing: no file may drop a fixed rule"),
        ("no longer fixed", "F-08 must be marked fixed"),
        ("blocks instead", "F-08: the verdict of a fixed rule is set in code: APPROVAL, not BLOCK"),
        ("another approver", "F-08: the approver role of a fixed rule is set in code: purchasing_manager, not finance"),
        ("reads a profile setting", "F-08: a fixed rule may not read 'profile.auto_order_enabled'"),
        ("judged per order", "fixed rule F-08 is missing its part judged per line"),
    ],
)
def test_a_rules_file_that_drops_or_weakens_f08_is_rejected(
    case: str, message: str, rules_data: Callable[[], dict[str, Any]]
) -> None:
    data = rules_data()
    _break(data, case)

    with pytest.raises(PolicyLoadError) as raised:
        parse_rulebook(data)

    assert any(message in problem for problem in raised.value.problems)


def test_a_profile_that_names_f08_is_rejected_at_start_up(
    profile_data: Callable[[str], dict[str, Any]], write_yaml: Callable[[str, Any], Path], tmp_path: Path,
) -> None:
    write_yaml("profiles/hotel-kitchen.yaml", {**profile_data("hotel-kitchen"), "claims": {"f-08": "off"}})

    with pytest.raises(PolicyLoadError, match="names fixed rule F-08"):
        RulePolicyEngine.from_files(RULES_PATH, tmp_path / "profiles")


def test_the_authority_says_that_a_substitute_that_lacks_a_claim_goes_to_a_human(
    engine: RulePolicyEngine, hotel: BuyerProfile, ward: BuyerProfile
) -> None:
    for profile in (hotel, ward):
        authority = engine.describe_authority(profile)
        f08 = next(rule for rule in authority.rules if rule.rule_id == "F-08")

        assert f08.fixed and f08.verdict is Verdict.APPROVAL
        assert f08.approver_role is ApproverRole.DIETITIAN  # both name one
        assert f08.sentence == (
            "A substitute that lacks a dietary claim of the product it replaces, for example lactose-free, "
            "always goes to the dietitian."
        )
        always = next(line for line in authority.summary if line.startswith("Always to a human"))
        assert "a substitute that lacks a dietary claim of the product it replaces" in always


def test_the_hash_covers_f08(
    engine: RulePolicyEngine, hotel: BuyerProfile, rules_data: Callable[[], dict[str, Any]],
    write_yaml: Callable[[str, Any], Path],
) -> None:
    data = rules_data()
    _f08(data)["justification"] += " Reworded."

    reworded = RulePolicyEngine.from_files(write_yaml("reworded.yaml", data), PROFILES_DIR)

    assert reworded.policy_hash(hotel) != engine.policy_hash(hotel)
