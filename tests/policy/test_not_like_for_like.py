"""F-12 does what the buyer is told: the agent never chooses alone a substitute that is not a like-for-like
replacement (check CK3 of Sunday 15 Nov 2026, decision B64).

The page says "whatever you set, the agent never chooses on its own a substitute that is not a like-for-like
replacement", and the rules file says the same of its third group. Measured on the demo clock in replay, with
ordering alone switched on: the hotel had 100 x `475224` ordered by the agent for `473609` while the line said "Not
a like-for-like replacement: a different formula", and the ward (with same-category substitutes accepted) had 100 L
of a rice drink ordered for a barista oat drink. F-12 fired on the offer's `last_resort` mark only, which the offer
sets for a lost claim or another kind of product; a verdict of "not like for like" for use or formula set nothing.

Now the fact F-12 reads is true for every substitute whose replaceability verdict is not REPLACEABLE. The lines
below are the two measured ones, as the offer built them.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest

from tta.contracts.common import AllergenRelation, ApproverRole, SubstitutionScope, Verdict
from tta.contracts.offer import OfferLine, OfferOption, SubstituteInfo
from tta.contracts.policy import BuyerProfile, PolicyContext
from tta.contracts.product import FormulaCheck, FormulaOutcome, NutrientDifference, ReplaceCheck, ReplaceVerdict
from tta.policy import RULES_PATH, RulePolicyEngine, load_rulebook, rule_groups
from tta.policy.facts import OrderScope, read_fact
from tta.policy.validation import FIXED_RULES

OAT = "Oddlygood® Barista oat drink 1 l UHT gluten free (473609)"
FAZER = "Fazer Aito Professional Barista Oat drink, gluten-free 1L UHT"
RICE = "Alpro Rice drink 1L"
# The reasons as the offer wrote them on the two measured lines (demo clock, replay, Sunday 15 Nov 2026).
FAZER_FORMULA = (
    "a different formula (contains OAT base (water, gluten-free OAT 10%), stabilizer (gellan gum), iodized salt "
    "and 2 more, which the product asked for does not; lacks gluten-free OAT flour 10 %, salt, iodine and 2 more, "
    "which the product asked for contains; carbohydrate 7.8 g, not 6.6 g, sugars 1.6 g, not 3.5 g)"
)
RICE_USE = "not made for coffee, as the product asked for is"
RICE_FORMULA = (
    "a different formula (contains Rice base (98.4%) (water, rice (12.5%)), sunflower oil, Sea salt and 3 more, "
    "which the product asked for does not; lacks gluten-free OAT flour 10 %, rapeseed oil, salt and 3 more, which "
    "the product asked for contains; fat 1 g, not 3 g, protein 0.1 g, not 1.2 g, carbohydrate 9.5 g, not 6.6 g)"
)
DIFFERENT = FormulaCheck(
    outcome=FormulaOutcome.DIFFERENT,
    differences=(
        NutrientDifference(nutrient="protein", original=Decimal("1.2"), other=Decimal("0.1"), within_tolerance=False),
    ),
    sentence="Different formula: protein 0.1 g, not 1.2 g per 100 ml.",
)
NOT_KNOWN = FormulaCheck(outcome=FormulaOutcome.NOT_KNOWN, sentence="The formula cannot be compared.")
SAME = FormulaCheck(outcome=FormulaOutcome.SAME_BRAND, sentence="Same formula within our tolerance.")
PERSON_DECIDES = "A person decides whether it will do."


def _not_like(*reasons: str, **flags: bool) -> ReplaceCheck:
    return ReplaceCheck(
        verdict=ReplaceVerdict.NOT_LIKE_FOR_LIKE, reasons=reasons,
        sentence=f"Not a like-for-like replacement: {'; '.join(reasons)}.", **flags,
    )


@pytest.fixture
def stand_in(
    make_line: Callable[..., OfferLine], make_substitute: Callable[..., SubstituteInfo],
    make_allergen_check: Callable[..., Any],
) -> Callable[..., OfferLine]:
    """A substitute for the barista oat drink `473609` that the offer does not mark `last_resort`: same category,
    not listed by Valio Aimo, no allergen added, no claim lost, every statement confirmed."""

    def build(
        product_id: str, name: str, check: ReplaceCheck | None, formula: FormulaCheck | None = DIFFERENT, *,
        free_from: tuple[str, ...] = (), **substitute: Any,
    ) -> OfferLine:
        info = make_substitute(**{"listed": False, "category_distance": 0, **substitute}).model_copy(update={
            "original_name": "Oddlygood® Barista oat drink 1 l UHT gluten free", "last_resort": False,
            "replaceable": check, "formula": formula,
        })
        allergens = make_allergen_check(dict.fromkeys(free_from, AllergenRelation.FREE_FROM)) if free_from else None
        return make_line(product_id, name, substitute=info, allergen_check=allergens)

    return build


@pytest.fixture
def hotel_alone(hotel: BuyerProfile) -> BuyerProfile:
    """Reproduction A: the hotel with one setting changed, ordering alone on. It accepts a same-category substitute."""
    return hotel.model_copy(update={"auto_order_enabled": True})


@pytest.fixture
def ward_alone(ward: BuyerProfile) -> BuyerProfile:
    """Reproduction B: the ward with ordering alone on and same-category substitutes accepted."""
    return ward.model_copy(update={
        "auto_order_enabled": True, "substitution_without_approval": SubstitutionScope.SAME_CATEGORY,
    })


# --- the two measured orders ---------------------------------------------------------------------------------


def test_reproduction_a_the_hotel_with_ordering_alone_on_a_substitute_of_another_formula_goes_to_a_person(
    engine: RulePolicyEngine, hotel_alone: BuyerProfile, stand_in: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    line = stand_in("475224", FAZER, _not_like(FAZER_FORMULA))

    decision = engine.evaluate(make_option((line,), net="174.00"), hotel_alone, make_context())

    assert line.substitute.last_resort is False and line.substitute.claims_lost == ()  # nothing F-12 used to read
    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-12",)
    f12 = decision.fired[0]
    assert f12.fixed and f12.product_id == "475224" and f12.title == "A substitute is not a like-for-like replacement"
    assert f12.sentence == (
        f"{FAZER} (475224) would replace {OAT} and is not a like-for-like replacement: {FAZER_FORMULA}. "
        f"{PERSON_DECIDES}"
    )
    assert f12.facts["line.substitute_last_resort"] is True
    assert f12.facts["line.substitute_replace_verdict"] == "NOT_LIKE_FOR_LIKE"
    # One person holds every role of the hotel: nothing changes in who is asked.
    assert f12.approver_role is ApproverRole.PURCHASING_MANAGER
    assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)
    assert decision.sentence.endswith(f"{PERSON_DECIDES[:-1]} (F-12). It needs the purchasing manager.")


def test_reproduction_b_the_ward_with_same_category_substitutes_a_rice_drink_for_a_barista_drink_goes_to_the_dietitian(
    engine: RulePolicyEngine, ward_alone: BuyerProfile, stand_in: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    line = stand_in("473424", RICE, _not_like(RICE_USE, RICE_FORMULA, other_use=True), free_from=("AM", "AW"))

    decision = engine.evaluate(make_option((line,), net="236.00"), ward_alone, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-12",)
    assert decision.fired[0].sentence == (
        f"{RICE} (473424) would replace {OAT} and is not a like-for-like replacement: {RICE_USE}; {RICE_FORMULA}. "
        f"{PERSON_DECIDES}"
    )
    assert "protein 0.1 g, not 1.2 g" in decision.sentence
    # A formula or nutrients that differ are the dietitian's question where the customer has one (decision B66).
    assert decision.fired[0].approver_role is ApproverRole.DIETITIAN
    assert decision.required_roles == (ApproverRole.DIETITIAN,)
    assert decision.sentence.endswith("(F-12). It needs the dietitian.")
    assert decision.fired[0].facts["profile.dietitian_is_second_person"] is True  # what decided who signs


def test_the_dearer_substitute_of_check_c1_8_is_not_like_for_like_and_goes_to_a_person(
    engine: RulePolicyEngine, hotel_alone: BuyerProfile, make_line: Callable[..., OfferLine],
    make_substitute: Callable[..., SubstituteInfo], make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    """Hotel, ordering alone on: 40 x 470341 "Visp 250ml" for €50.40 in place of 10 x cooking cream 460697 for
    €24.80, by the agent alone, no rule fired (measured on the demo clock, 15 Nov 2026). The offer's own verdict on
    that line was "not like for like: a different formula", so this rule is what stops it."""
    formula = (
        "a different formula (contains kovetettu kookos- ja rapsiöljy, maltodextriini, suola and 5 more, which the "
        "product asked for does not; lacks rapsiöljy, stabilointiaine E415, jodioitu suola and 1 more, which the "
        "product asked for contains; fat 23 g, not 13 g, saturated fat 22 g, not 1.6 g, carbohydrate 11 g, not 5.8 g, "
        "sugars 2.3 g, not 3.6 g)"
    )
    info = make_substitute(listed=False, replaceable=_not_like(formula, type_not_judged=True)).model_copy(update={
        "original_id": "460697", "original_name": "Oatly iMat for Cooking 1L", "formula": DIFFERENT,
    })
    visp = make_line("470341", "Oatly iMat Visp 250ml", quantity="40", unit_net_price="1.26", substitute=info)

    decision = engine.evaluate(make_option((visp,), net="50.40"), hotel_alone, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-12",)
    assert decision.fired[0].sentence == (
        "Oatly iMat Visp 250ml (470341) would replace Oatly iMat for Cooking 1L (460697) and is not a like-for-like "
        f"replacement: {formula}. {PERSON_DECIDES}"
    )


@pytest.mark.parametrize("ordering_alone", [True, False])
def test_with_ordering_alone_off_the_rule_names_itself_too(
    ordering_alone: bool, engine: RulePolicyEngine, hotel: BuyerProfile, stand_in: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    profile = hotel.model_copy(update={"auto_order_enabled": ordering_alone})

    decision = engine.evaluate(make_option((stand_in("475224", FAZER, _not_like(FAZER_FORMULA)),)), profile,
                               make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-12",)


def test_no_setting_lets_a_substitute_that_is_not_like_for_like_through(
    engine: RulePolicyEngine, hotel_alone: BuyerProfile, stand_in: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    widest = hotel_alone.model_copy(update={"max_order_net_eur": Decimal(1_000_000), "min_fill_ratio": Decimal(0)})

    for listed in (True, False):  # a pair Valio Aimo lists is judged like any other
        line = stand_in("475224", FAZER, _not_like(FAZER_FORMULA), listed=listed)
        decision = engine.evaluate(make_option((line,)), widest, make_context())
        assert "F-12" in decision.rule_ids and decision.verdict is Verdict.APPROVAL


# --- the three verdicts -----------------------------------------------------------------------------------------


def test_a_substitute_judged_replaceable_can_still_be_ordered_alone(
    engine: RulePolicyEngine, hotel_alone: BuyerProfile, stand_in: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    """The autonomous path stays: same type, use, flavour and formula, no claim lost, every statement confirmed."""
    check = ReplaceCheck(
        verdict=ReplaceVerdict.REPLACEABLE, sentence="Replaceable: same type, same use, no flavour named, same "
        "formula within tolerance.",
    )
    line = stand_in("475224", FAZER, check, SAME)
    option = make_option((line,))

    decision = engine.evaluate(option, hotel_alone, make_context())

    assert decision.verdict is Verdict.AUTO and decision.fired == ()
    scope = OrderScope(option, hotel_alone, make_context(), substitution_scopes={})
    assert read_fact("line.substitute_last_resort", scope, line) is False
    assert read_fact("line.substitute_replace_verdict", scope, line) == "REPLACEABLE"


@pytest.mark.parametrize(
    ("type_not_judged", "formula", "reasons"),
    [
        (False, NOT_KNOWN, "its formula cannot be compared with that of the product asked for"),
        (True, SAME, "only its category could be compared with the product asked for, not its kind of product"),
        (True, NOT_KNOWN, "only its category could be compared with the product asked for, not its kind of product; "
                          "its formula cannot be compared with that of the product asked for"),
    ],
    ids=["formula not known", "type not judged", "both"],
)
def test_replaceable_as_far_as_the_data_shows_is_not_shown_to_be_like_for_like_and_goes_to_a_person(
    type_not_judged: bool, formula: FormulaCheck, reasons: str,
    engine: RulePolicyEngine, hotel_alone: BuyerProfile, stand_in: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    """Most catalog products have none of our product types: for them the offer's best verdict is "as far as the
    data shows", and that is not "like for like"."""
    check = ReplaceCheck(
        verdict=ReplaceVerdict.NOT_SHOWN, type_not_judged=type_not_judged,
        sentence="Replaceable as far as the data shows: same category, same use, no flavour named; not shown.",
    )

    decision = engine.evaluate(make_option((stand_in("475224", FAZER, check, formula),)), hotel_alone, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-12",)
    assert decision.fired[0].sentence == (
        f"{FAZER} (475224) would replace {OAT} and is not shown to be a like-for-like replacement: {reasons}. "
        f"{PERSON_DECIDES}"
    )
    assert decision.fired[0].facts["line.substitute_replace_verdict"] == "NOT_SHOWN"


def test_a_substitute_that_carries_no_like_for_like_check_is_a_missing_fact_never_a_pass(
    engine: RulePolicyEngine, hotel_alone: BuyerProfile, stand_in: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    """A line stored before the offer carried the check: no data means unknown, not "like for like"."""
    decision = engine.evaluate(make_option((stand_in("475224", FAZER, None, None),)), hotel_alone, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-03",)
    assert decision.fired[0].sentence == (
        f"The like-for-like check of {FAZER} (475224) is missing (the offer carries no like-for-like check for "
        "this substitute), so rule F-12 cannot be checked."
    )


# --- one fact, one sentence -------------------------------------------------------------------------------------


def test_where_the_formula_matters_the_difference_of_formula_is_said_once_by_the_formula_rule(
    engine: RulePolicyEngine, hotel_alone: BuyerProfile, stand_in: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    matters = hotel_alone.model_copy(update={"formula_matters": True})
    only_formula = stand_in("475224", FAZER, _not_like(FAZER_FORMULA))
    use_and_formula = stand_in("473424", RICE, _not_like(RICE_USE, RICE_FORMULA, other_use=True))

    one = engine.evaluate(make_option((only_formula,)), matters, make_context())
    two = engine.evaluate(make_option((use_and_formula,)), matters, make_context())

    assert one.verdict is Verdict.APPROVAL and one.rule_ids == ("F-11",)  # F-12 has no reason of its own left
    assert two.rule_ids == ("F-11", "F-12")
    assert two.fired[1].sentence == (
        f"{RICE} (473424) would replace {OAT} and is not a like-for-like replacement: {RICE_USE}. {PERSON_DECIDES}"
    )


def test_where_the_formula_matters_a_formula_that_cannot_be_compared_is_said_once_by_the_formula_rule(
    engine: RulePolicyEngine, hotel_alone: BuyerProfile, stand_in: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    matters = hotel_alone.model_copy(update={"formula_matters": True})
    check = ReplaceCheck(verdict=ReplaceVerdict.NOT_SHOWN, sentence="Replaceable as far as the data shows.")

    decision = engine.evaluate(make_option((stand_in("475224", FAZER, check, NOT_KNOWN),)), matters, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-11",)


# --- who is asked (decision B66) --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("profile_id", "role"),
    [
        ("allergy-ward", ApproverRole.DIETITIAN), ("school-kitchen", ApproverRole.DIETITIAN),
        ("hotel-kitchen", ApproverRole.PURCHASING_MANAGER), ("bakery-cafe", ApproverRole.PURCHASING_MANAGER),
    ],
)
def test_a_formula_that_differs_is_the_dietitians_question_where_the_customer_has_a_dietitian_of_its_own(
    profile_id: str, role: ApproverRole, engine: RulePolicyEngine, stand_in: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    """F-11 and F-12 both. At the hotel and the bakery one person holds every role: nothing changes there."""
    profile = engine.get_profile(profile_id)
    free_from = tuple(profile.excluded_allergens)
    by_formula = stand_in("475224", FAZER, _not_like(FAZER_FORMULA), free_from=free_from)
    by_use = stand_in("473424", RICE, _not_like(RICE_USE, other_use=True), SAME, free_from=free_from)
    matters = profile.model_copy(update={"formula_matters": True})

    formula = engine.evaluate(make_option((by_formula,)), matters, make_context())
    use = engine.evaluate(make_option((by_use,)), profile, make_context())

    asked = {rule.rule_id: rule.approver_role for rule in (*formula.fired, *use.fired)}
    assert asked["F-11"] is role and asked["F-12"] is role
    assert role in formula.required_roles and role in use.required_roles


def test_the_roles_f11_and_f12_may_ask_are_pinned_in_code_and_written_in_the_rules_file() -> None:
    by_id = {rule.id: rule for rule in load_rulebook(RULES_PATH).rules}

    for rule_id in ("F-11", "F-12"):
        assert FIXED_RULES[rule_id].approver_role is ApproverRole.PURCHASING_MANAGER
        assert FIXED_RULES[rule_id].other_roles == (ApproverRole.DIETITIAN,)
        assert [entry.role for entry in by_id[rule_id].approver_role_when] == [ApproverRole.DIETITIAN]
        assert by_id[rule_id].fixed and by_id[rule_id].verdict is Verdict.APPROVAL


# --- what the customer is told ----------------------------------------------------------------------------------


def test_the_statement_the_customer_reads_and_the_authority_say_the_same_thing(engine: RulePolicyEngine) -> None:
    group = next(group for group in rule_groups() if "F-12" in group.rule_ids)
    assert group.statement == "A substitute that is not a like-for-like replacement goes to a person."

    for profile_id in engine.profile_ids():
        authority = engine.describe_authority(engine.get_profile(profile_id))
        f12 = next(rule for rule in authority.rules if rule.rule_id == "F-12")
        assert f12.title == "A substitute is not a like-for-like replacement"
        assert "not a like-for-like replacement" in f12.sentence and "whatever" in f12.sentence, profile_id
        assert any("a substitute that is not a like-for-like replacement" in line for line in authority.summary)
