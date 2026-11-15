"""One fact, one sentence: F-08, F-11 and F-12 on the same line do not say the same thing twice.

A lost dietary claim makes a substitute a last resort, so F-08 and F-12 both fired on it and the person read the
claim twice. The same for a formula that differs where the formula matters (F-11). Now the rule that owns the
fact says it: F-12 leaves that reason out and, when no reason of its own is left, does not fire. The line goes
to a person either way; these tests build a line for each combination.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from decimal import Decimal

import pytest

from tta.contracts.common import Verdict
from tta.contracts.offer import OfferLine, OfferOption, SubstituteInfo
from tta.contracts.policy import BuyerProfile, PolicyContext
from tta.contracts.product import FormulaCheck, FormulaOutcome, NutrientDifference, ReplaceCheck, ReplaceVerdict
from tta.offers.substitute_wording import replace_reasons, replace_sentence
from tta.policy import RulePolicyEngine
from tta.policy.last_resort_facts import CLAIM_REASON_PREFIX, FORMULA_REASON_FAT_SOURCE, FORMULA_REASON_PREFIX

STAND_IN = "Oddlygood Barista nutty vanilla (474724)"
ORIGINAL = "Oddlygood Barista oat drink (473609)"
FLAVOUR = "flavoured with nut and vanilla; the product asked for is not flavoured"
CLAIM = "it does not carry the claim FREE_FROM_GLUTEN"
FORMULA = "a different formula (fat 15 g, not 36 g)"
VARIANT = "it cannot be shown to be like for like: its name adds “Barista”, which the data does not explain"
VARIANT_SAID = VARIANT.replace("“", "'").replace("”", "'")  # read as data: a quotation mark becomes an apostrophe
DIFFERENT = FormulaCheck(
    outcome=FormulaOutcome.DIFFERENT,
    differences=(NutrientDifference(nutrient="fat", original=Decimal(36), other=Decimal(15), within_tolerance=False),),
    sentence="Different formula: fat 15 g, not 36 g per 100 g.",
)
F08 = f"{STAND_IN} would replace {ORIGINAL} but is not marked gluten-free, as the product asked for is."
F11_START = f"{STAND_IN} would replace {ORIGINAL} where the formula matters"


def f12(reasons: str) -> str:
    return (
        f"{STAND_IN} would replace {ORIGINAL} and is not a like-for-like replacement: {reasons}. A person decides "
        "whether it will do."
    )


@pytest.fixture
def alone(hotel: BuyerProfile) -> BuyerProfile:
    """Ordering alone on, same-category substitutes accepted: only the fixed rules stand between the line and
    an order nobody saw."""
    return hotel.model_copy(update={"auto_order_enabled": True})


@pytest.fixture
def last_resort(
    make_line: Callable[..., OfferLine], make_substitute: Callable[..., SubstituteInfo]
) -> Callable[..., OfferLine]:
    def build(
        reasons: Sequence[str], *, claims_lost: Sequence[str] = (), formula: FormulaCheck | None = None,
        one_per_entry: bool = True,
    ) -> OfferLine:
        """A last resort as the offer builds it: each reason in `ReplaceCheck.reasons` and all of them in the
        sentence. `one_per_entry=False`: a line stored with the sentence only."""
        check = ReplaceCheck(
            verdict=ReplaceVerdict.NOT_LIKE_FOR_LIKE, reasons=tuple(reasons) if one_per_entry else (),
            sentence=f"Not a like-for-like replacement: {'; '.join(reasons)}.",
        )
        stand_in = make_substitute(listed=False, claims_lost=claims_lost).model_copy(
            update={"last_resort": True, "replaceable": check, "formula": formula}
        )
        return make_line("474724", "Oddlygood Barista nutty vanilla", substitute=stand_in)

    return build


# What the person reads for each combination: the rules that fire and, where F-12 fires, its whole sentence.
# `matters`: the buyer says the formula matters on every line (the bakery's setting), so F-11 looks at the line.
CASES = [
    # (case, reasons of the offer, claims lost, formula check, matters, rules fired, F-12's sentence or None)
    ("only the lost claim", [CLAIM], ["FREE_FROM_GLUTEN"], None, False, ("F-08",), None),
    ("the lost claim and a flavour", [FLAVOUR, CLAIM], ["FREE_FROM_GLUTEN"], None, False, ("F-08", "F-12"),
     f12(FLAVOUR)),
    ("only a flavour", [FLAVOUR], [], None, False, ("F-12",), f12(FLAVOUR)),
    ("only an unexplained variant", [VARIANT], [], None, False, ("F-12",), f12(VARIANT_SAID)),
    ("only the formula, where it matters", [FORMULA], [], DIFFERENT, True, ("F-11",), None),
    ("the formula where it matters and a flavour", [FLAVOUR, FORMULA], [], DIFFERENT, True, ("F-11", "F-12"),
     f12(FLAVOUR)),
    # Where the formula does not matter F-11 is silent, so the difference is F-12's to say: it is said once.
    ("only the formula, where it does not matter", [FORMULA], [], DIFFERENT, False, ("F-12",), f12(FORMULA)),
    ("the claim and the formula, where it matters", [CLAIM, FORMULA], ["FREE_FROM_GLUTEN"], DIFFERENT, True,
     ("F-08", "F-11"), None),
    ("the claim, the formula where it matters and a flavour", [FLAVOUR, CLAIM, FORMULA], ["FREE_FROM_GLUTEN"],
     DIFFERENT, True, ("F-08", "F-11", "F-12"), f12(FLAVOUR)),
]


@pytest.mark.parametrize(("case", "reasons", "lost", "formula", "matters", "fired", "f12_sentence"), CASES,
                         ids=[case[0] for case in CASES])
def test_each_fact_of_a_last_resort_is_said_by_one_rule(
    case: str, reasons: list[str], lost: list[str], formula: FormulaCheck | None, matters: bool,
    fired: tuple[str, ...], f12_sentence: str | None,
    engine: RulePolicyEngine, alone: BuyerProfile, last_resort: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    profile = alone.model_copy(update={"formula_matters": matters})
    line = last_resort(reasons, claims_lost=lost, formula=formula)

    decision = engine.evaluate(make_option((line,)), profile, make_context())

    assert decision.verdict is Verdict.APPROVAL  # whatever is said once, the line never passes alone
    assert decision.rule_ids == fired
    sentences = {rule.rule_id: rule.sentence for rule in decision.fired}
    assert sentences.get("F-12") == f12_sentence
    if "F-08" in fired:
        assert sentences["F-08"] == F08
    if "F-11" in fired:
        assert sentences["F-11"].startswith(F11_START) and "fat 15 g, not 36 g" in sentences["F-11"]
    said = " ".join(sentences.values())
    assert said.count("gluten") <= 1 and said.count("fat 15 g, not 36 g") <= 1


def test_reasons_that_cannot_be_told_apart_are_all_kept(
    engine: RulePolicyEngine, alone: BuyerProfile, last_resort: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    """A line stored with the offer's sentence and no list of reasons: saying the claim twice is the lesser
    fault, leaving the flavour out is not."""
    line = last_resort([CLAIM, FLAVOUR], claims_lost=["FREE_FROM_GLUTEN"], one_per_entry=False)

    decision = engine.evaluate(make_option((line,)), alone, make_context())

    assert decision.rule_ids == ("F-08", "F-12")
    assert decision.fired[1].sentence == f12(f"{CLAIM}; {FLAVOUR}")


def test_the_reasons_left_out_are_the_ones_the_offer_writes() -> None:
    """The offer's wording is not ours (`tta.offers.substitute_wording`): this fails when it changes, before a
    reason is said twice or, worse, a reason of another kind is left out."""
    plain = ReplaceCheck(verdict=ReplaceVerdict.NOT_LIKE_FOR_LIKE, sentence="")
    kept = FormulaCheck(outcome=FormulaOutcome.OTHER_BRAND, sentence="Same formula.")
    other_fat = FormulaCheck(outcome=FormulaOutcome.DIFFERENT, fat_source_differs=True, sentence="Different formula.")

    assert replace_reasons(plain, kept, ("FREE_FROM_LACTOSE",), listed=False) == (
        f"{CLAIM_REASON_PREFIX} FREE_FROM_LACTOSE",
    )
    assert replace_reasons(plain, kept, ("VEGAN", "FREE_FROM_SOY"), listed=False)[0].startswith(CLAIM_REASON_PREFIX)
    assert replace_reasons(plain, DIFFERENT, (), listed=False)[0].startswith(FORMULA_REASON_PREFIX)
    assert replace_reasons(plain, other_fat, (), listed=False) == (FORMULA_REASON_FAT_SOURCE,)
    sentence = replace_sentence(plain, ReplaceVerdict.NOT_LIKE_FOR_LIKE, [FLAVOUR], same_category=True)
    assert sentence == f"Not a like-for-like replacement: {FLAVOUR}."
