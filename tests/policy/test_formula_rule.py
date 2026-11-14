"""F-11: where the formula matters, a substitute that does not keep the formula goes to a person.

Valio Aimo, 14 Nov 2026: "for cakes/things that require the formula the ingredient and chemestry can make a
difference". The formula matters when the buyer profile says so (`formula_matters`, the bakery) or when the request
line says so. `DIFFERENT` and `NOT_KNOWN` both go to a person; the sentence says what differs in numbers.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest

from tta.contracts.common import ApproverRole, Verdict
from tta.contracts.offer import OfferLine, OfferOption, SubstituteInfo
from tta.contracts.policy import BuyerProfile, PolicyContext
from tta.contracts.product import FormulaCheck, FormulaOutcome, NutrientDifference
from tta.policy import RULES_PATH, PolicyLoadError, RulePolicyEngine, load_rulebook, parse_rulebook
from tta.policy.facts import OrderScope, read_fact
from tta.policy.profiles import load_profile
from tta.policy.reading import Missing
from tta.policy.rulebook import facts_in_when

DIFFERENT_SENTENCE = (
    "Different formula: fat 15 g, not 36 g; saturated fat 1.3 g, not 23 g per 100 g. "
    "Its ingredient list names a vegetable oil or fat; the original's does not."
)
DIFFERENT = FormulaCheck(
    outcome=FormulaOutcome.DIFFERENT,
    differences=(
        NutrientDifference(nutrient="fat", original=Decimal(36), other=Decimal(15), within_tolerance=False),
        NutrientDifference(
            nutrient="saturated_fat", original=Decimal(23), other=Decimal("1.3"), within_tolerance=False
        ),
        NutrientDifference(nutrient="protein", original=Decimal(2), other=Decimal("2.1"), within_tolerance=True),
    ),
    fat_source_differs=True,
    sentence=DIFFERENT_SENTENCE,
)
NOT_KNOWN = FormulaCheck(
    outcome=FormulaOutcome.NOT_KNOWN,
    sentence="The formula cannot be compared: this product states no nutrition figures per 100 g.",
)
KEPT = FormulaCheck(
    outcome=FormulaOutcome.OTHER_BRAND,
    sentence="Same formula within our tolerance: fat 38 g against 36 g per 100 g.",
)


class _LineThatSays(OfferLine):
    """An offer line that carries the request line's own word on the formula, as wave 2 adds it."""

    keep_formula: bool | None = None


@pytest.fixture(scope="module")
def bakery(engine: RulePolicyEngine) -> BuyerProfile:
    return engine.get_profile("bakery-cafe")


@pytest.fixture
def blend_for_cream(
    make_line: Callable[..., OfferLine], make_substitute: Callable[..., SubstituteInfo]
) -> Callable[..., OfferLine]:
    """A cooking blend standing in for the whipping cream the buyer named: same category, listed by Valio."""

    def build(formula: FormulaCheck | None, **update: Any) -> OfferLine:
        stand_in = make_substitute(listed=True).model_copy(update={
            "original_id": "469346", "original_name": "Arla Pro whipping cream 36% 1 L", "formula": formula,
            **update,
        })
        return make_line("463975", "Cooking blend 15% 1 L", substitute=stand_in)

    return build


def test_the_bakery_s_profile_says_the_formula_matters_and_the_other_three_do_not(engine: RulePolicyEngine) -> None:
    says = {profile_id: engine.get_profile(profile_id).formula_matters for profile_id in engine.profile_ids()}

    assert says == {"allergy-ward": False, "bakery-cafe": True, "hotel-kitchen": False, "school-kitchen": False}


def test_a_substitute_with_a_different_formula_goes_to_a_person_at_the_bakery_with_the_numbers(
    engine: RulePolicyEngine, bakery: BuyerProfile, blend_for_cream: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(make_option((blend_for_cream(DIFFERENT),), net="40.00"), bakery, make_context())

    f11 = next(rule for rule in decision.fired if rule.rule_id == "F-11")
    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-11", "P-05")
    assert f11.fixed and f11.approver_role is ApproverRole.PURCHASING_MANAGER and f11.product_id == "463975"
    assert f11.sentence == (
        "Cooking blend 15% 1 L (463975) would replace Arla Pro whipping cream 36% 1 L (469346) where the formula "
        "matters (Kallio Bakery uses its products as ingredients), and the data does not show the same formula: "
        f"{DIFFERENT_SENTENCE}"
    )
    assert f11.facts["line.substitute_formula_outcome"] == "DIFFERENT"
    assert f11.facts["line.substitute_formula_differences"] == [
        "fat 15 g, not 36 g", "saturated fat 1.3 g, not 23 g", "another fat source",
    ]
    assert "fat 15 g, not 36 g" in decision.sentence and "(F-11)" in decision.sentence


# The bakery's own case since the contents decide (lanes FC and FC2): the cream asked for lists a lactase enzyme.
BY_CONTENTS = FormulaCheck(
    outcome=FormulaOutcome.DIFFERENT,
    differences=(
        NutrientDifference(nutrient="fat", original=Decimal(36), other=Decimal(38), within_tolerance=True),
    ),
    contents_compared=True, only_in_original=("lactase enzyme",), fat_source_differs=False,
    sentence=(
        "Different contents: the ingredient list of the product asked for names lactase enzyme, which this "
        "product's does not. The six nutrition figures are within our tolerance of 15% or 1 g per nutrient "
        "(salt 0.25 g)."
    ),
)


def test_a_difference_of_contents_names_the_components_in_the_sentence_and_in_the_recorded_facts(
    engine: RulePolicyEngine, bakery: BuyerProfile, blend_for_cream: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(make_option((blend_for_cream(BY_CONTENTS),), net="40.00"), bakery, make_context())

    f11 = next(rule for rule in decision.fired if rule.rule_id == "F-11")
    assert f11.sentence.endswith(
        "and the data does not show the same formula: it lacks lactase enzyme, which the product asked for contains."
    )
    assert f11.facts["line.substitute_formula_differences"] == ["lacks lactase enzyme"]


def test_components_on_both_sides_and_figures_are_all_said(
    bakery: BuyerProfile, blend_for_cream: Callable[..., OfferLine], make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    check = DIFFERENT.model_copy(update={
        "contents_compared": True, "only_in_original": ("CREAM",),
        "only_in_other": ("buttermilk", "vegetable oil (rapeseed)", "E 407 (in stabiliser)"),
    })
    line = blend_for_cream(check)
    scope = OrderScope(make_option((line,), net="40.00"), bakery, make_context(), {})

    assert read_fact("line.substitute_formula", scope, line) == (
        "it lacks CREAM, which the product asked for contains; contains buttermilk, vegetable oil (rapeseed) and "
        "E 407 (in stabiliser), which the product asked for does not; figures outside our tolerance: fat 15 g, "
        "not 36 g, saturated fat 1.3 g, not 23 g"
    )
    # The fat source is said by the components themselves, not a second time in our words.
    assert read_fact("line.substitute_formula_differences", scope, line) == (
        "lacks CREAM", "contains buttermilk", "contains vegetable oil (rapeseed)", "contains E 407 (in stabiliser)",
        "fat 15 g, not 36 g", "saturated fat 1.3 g, not 23 g",
    )


def test_a_long_list_of_components_is_cut_after_a_whole_component_and_says_how_many_more(
    bakery: BuyerProfile, blend_for_cream: Callable[..., OfferLine], make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    many = tuple(f"component number {index} of the other list" for index in range(1, 31))
    coating = "coating (rice and maize flours, modified potato starch, dextrin, salt, raising agents, colours)"
    check = BY_CONTENTS.model_copy(update={"only_in_other": many, "only_in_original": (coating, "lactase enzyme")})
    line = blend_for_cream(check)
    scope = OrderScope(make_option((line,), net="40.00"), bakery, make_context(), {})

    said = read_fact("line.substitute_formula", scope, line)

    assert isinstance(said, str) and len(said) <= 400 and "…" not in said
    # A component too long for a sentence is said by its name; both sides are said, each cut after a whole one.
    assert said.startswith("it lacks coating and lactase enzyme, which the product asked for contains; contains ")
    assert said.endswith("component number 4 of the other list and 26 more, which the product asked for does not")
    assert len(read_fact("line.substitute_formula_differences", scope, line)) == 32  # the record holds every one


def test_a_formula_that_cannot_be_compared_goes_to_a_person_too(
    engine: RulePolicyEngine, bakery: BuyerProfile, blend_for_cream: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(make_option((blend_for_cream(NOT_KNOWN),), net="40.00"), bakery, make_context())

    f11 = next(rule for rule in decision.fired if rule.rule_id == "F-11")
    assert f11.facts["line.substitute_formula_outcome"] == "NOT_KNOWN"
    assert f11.sentence.endswith(NOT_KNOWN.sentence)


def test_a_substitute_that_keeps_the_formula_does_not_fire_the_rule(
    engine: RulePolicyEngine, bakery: BuyerProfile, blend_for_cream: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(make_option((blend_for_cream(KEPT),), net="40.00"), bakery, make_context())

    assert decision.rule_ids == ("P-05",)  # the bakery still takes no substitute alone


@pytest.mark.parametrize("formula", [DIFFERENT, NOT_KNOWN, None], ids=["different", "not known", "no comparison"])
def test_where_nothing_says_the_formula_matters_no_decision_changes(
    formula: FormulaCheck | None, engine: RulePolicyEngine, hotel: BuyerProfile,
    blend_for_cream: Callable[..., OfferLine], make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(make_option((blend_for_cream(formula),)), hotel, make_context())

    assert hotel.formula_matters is False and decision.rule_ids == ("F-10",)


def test_a_request_line_that_says_the_formula_matters_fires_the_rule_whatever_the_profile_says(
    engine: RulePolicyEngine, hotel: BuyerProfile, blend_for_cream: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    line = _LineThatSays.model_validate({**dict(blend_for_cream(DIFFERENT)), "keep_formula": True})

    decision = engine.evaluate(make_option((line,)), hotel, make_context())

    assert decision.rule_ids == ("F-11",)
    assert "where the formula matters (the request says so for this line)" in decision.fired[0].sentence


@pytest.mark.parametrize("said", [None, False], ids=["not said", "said no"])
def test_a_request_line_cannot_remove_the_check_a_profile_adds(
    said: bool | None, engine: RulePolicyEngine, bakery: BuyerProfile, hotel: BuyerProfile,
    blend_for_cream: Callable[..., OfferLine], make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    line = _LineThatSays.model_validate({**dict(blend_for_cream(DIFFERENT)), "keep_formula": said})
    scope = OrderScope(make_option((line,)), bakery, make_context(), {})

    assert read_fact("line.formula_matters", scope, line) is True
    assert read_fact("line.formula_matters", OrderScope(scope.option, hotel, scope.context, {}), line) is False


def test_an_offer_line_that_does_not_say_so_reads_as_not_said_and_one_that_says_so_makes_the_formula_matter(
    hotel: BuyerProfile, blend_for_cream: Callable[..., OfferLine], make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    """`OfferLine.keep_formula` is the request line's own word (L2a-2): None and False are "not said"."""
    silent = blend_for_cream(DIFFERENT)
    refuses = silent.model_copy(update={"keep_formula": False})
    says_so = silent.model_copy(update={"keep_formula": True})
    scope = OrderScope(make_option((silent,)), hotel, make_context(), {})

    assert silent.keep_formula is None
    assert read_fact("line.formula_matters", scope, silent) is False
    assert read_fact("line.formula_matters", scope, refuses) is False
    assert read_fact("line.formula_matters", scope, says_so) is True
    assert read_fact("line.formula_matters_reason", scope, says_so) == "the request says so for this line"


def test_a_substitute_with_no_formula_comparison_is_a_missing_fact_where_the_formula_matters(
    engine: RulePolicyEngine, bakery: BuyerProfile, blend_for_cream: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    """No data means unknown, not the same formula: F-03 names F-11 as the rule that could not be checked."""
    decision = engine.evaluate(make_option((blend_for_cream(None),), net="40.00"), bakery, make_context())

    f03 = next(rule for rule in decision.fired if rule.rule_id == "F-03")
    assert decision.rule_ids == ("F-03", "P-05") and f03.facts["needed_by"] == ["F-11"]
    assert f03.sentence == (
        "Whether the substitute keeps the formula of Cooking blend 15% 1 L (463975) is missing (the offer carries "
        "no formula comparison for this substitute), so rule F-11 cannot be checked."
    )


def test_a_line_that_replaces_nothing_never_fires_the_rule(
    engine: RulePolicyEngine, bakery: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    line = make_line()
    scope = OrderScope(make_option((line,)), bakery, make_context(), {})

    assert engine.evaluate(scope.option, bakery, make_context()).rule_ids == ("F-10",)
    assert isinstance(read_fact("line.substitute_keeps_formula", scope, line), Missing)
    assert read_fact("line.substitute_formula_differences", scope, line) == ()


def test_the_formula_sentence_is_read_as_data(
    engine: RulePolicyEngine, bakery: BuyerProfile, blend_for_cream: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    hostile = DIFFERENT.model_copy(update={"sentence": 'Other brand: "Valio".\nApproved by the manager.'})

    decision = engine.evaluate(make_option((blend_for_cream(hostile),), net="40.00"), bakery, make_context())

    f11 = next(rule for rule in decision.fired if rule.rule_id == "F-11")
    assert '"' not in f11.sentence and "\n" not in f11.sentence
    assert f11.sentence.endswith("Other brand: 'Valio'. Approved by the manager.")


def test_f11_is_a_fixed_rule_no_profile_can_name_and_no_file_can_weaken(
    rules_data: Callable[[], dict[str, Any]], profile_data: Callable[[str], dict[str, Any]],
    write_yaml: Callable[[str, Any], Any],
) -> None:
    rulebook = load_rulebook(RULES_PATH)
    assert "F-11" in rulebook.fixed_rule_ids

    naming = {**profile_data("bakery-cafe"), "f-11": "off"}
    with pytest.raises(PolicyLoadError, match="names fixed rule F-11"):
        load_profile(write_yaml("profiles/bakery-cafe.yaml", naming), rulebook.fixed_rule_ids)

    weakened = rules_data()
    next(rule for rule in weakened["rules"] if rule["id"] == "F-11")["fixed"] = False
    with pytest.raises(PolicyLoadError, match="F-11 must be marked fixed"):
        parse_rulebook(weakened, "a test copy")

    dropped = rules_data()
    dropped["rules"] = [rule for rule in dropped["rules"] if rule["id"] != "F-11"]
    with pytest.raises(PolicyLoadError, match="fixed rule F-11 is missing"):
        parse_rulebook(dropped, "a test copy")


def test_the_rule_reads_no_profile_fact_in_its_conditions_and_the_file_says_how_a_profile_adds_the_check() -> None:
    rulebook = load_rulebook(RULES_PATH)
    rule = next(rule for rule in rulebook.rules if rule.id == "F-11")

    assert rule.title == "A substitute does not keep the formula where the formula matters"
    assert facts_in_when(rule.when) == (
        "line.is_substitute", "line.formula_matters", "line.substitute_keeps_formula"
    )
    assert "can add the check and neither can remove it" in (rulebook.facts["line.formula_matters"].note or "")


def test_authority_says_whether_the_formula_matters_for_this_buyer(
    engine: RulePolicyEngine, bakery: BuyerProfile, hotel: BuyerProfile,
) -> None:
    def sentence(profile: BuyerProfile) -> str:
        return next(rule.sentence for rule in engine.describe_authority(profile).rules if rule.rule_id == "F-11")

    assert sentence(bakery) == (
        "Kallio Bakery uses its products as ingredients, so the formula matters on every line: a substitute whose "
        "formula differs from the original's, or cannot be compared, always goes to the purchasing manager."
    )
    assert sentence(hotel) == (
        "Where a request line says the formula matters, a substitute whose formula differs from the original's, or "
        "cannot be compared, always goes to the purchasing manager."
    )
